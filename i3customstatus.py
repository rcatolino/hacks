#!/usr/bin/python3
import json
import os
import select
import socket
import subprocess
import sys

def get_essid(interface):
  output = subprocess.Popen(['iw', 'dev', interface, 'link'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.readlines()
  if output[0].decode().split(maxsplit=1)[0] == 'Connected':
    return output[1].decode().split(': ', 1)[1].rstrip('\n')
  return None

def get_network():
  net = []
  output = subprocess.Popen(['ifconfig'], stdout=subprocess.PIPE).stdout.readlines().__iter__()
  for line in output:
    try:
      [interface, _] = line.decode().split(':', 1)
    except ValueError:
      return

    address = None
    address6 = None
    loop = False
    essid = None
    for detail in output:
      if detail == b'\n':
        break

      [_, tag, value, _] = str(detail).split(maxsplit=3)
      if tag == 'inet':
        address = value
      elif tag == 'loop':
        loop = True

    if loop or address is None:
      continue

    net.append((interface, address, get_essid(interface)))
  return net

def get_bbswitch():
  state = None
  try:
    state = open('/proc/acpi/bbswitch', 'r').readline()[13:-1]
  except OSError:
    return None

  color = None
  if state == 'OFF':
    color = '#00FF00'
  else:
    color = '#1155FF'

  return dict(name = 'bbswitch', color = color, full_text = 'bbswitch: ' + state)

def add_plugins(status):
  plugins = []

  bbswitch_st = get_bbswitch()
  if bbswitch_st != None:
    plugins.append(bbswitch_st)

  for (i, net) in enumerate(get_network()):
    if net[2] is None:
      name = 'wired' + str(i)
      essid = ''
    else:
      name = 'wireless' + str(i)
      essid = ', ' + net[2]

    plugins.append(dict(name = name, color = '#00FF00', full_text = net[0] + ' : ' + net[1] + essid))

  return plugins + status

def loop():
  pipe_path = os.getenv('HOME') + '/.i3/i3status-pipe'
  if os.access(pipe_path, os.F_OK):
    os.unlink(pipe_path)

  pipe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
  pipe.bind(pipe_path)
  pipe.listen(1)
  custom_status = dict()
  status = []
  iteration = 0
  while True:
    (fo, _, _) = select.select([sys.stdin, pipe], [], [])
    for i in fo:
      if i == pipe:
        (lp, _) = i.accept()
        try:
          st = json.loads(lp.recv(512).decode())
        except ValueError:
          continue
        finally:
          lp.close()
        custom_status[st['name']] = st
        if st['name'] == 'irssi':
          iteration = 3

      else:
        if iteration != 0:
          iteration -= 1
        elif 'irssi' in custom_status:
          custom_status.pop('irssi')

        msg = i.readline()
        try:
          # i3status sends us a stream of json, we only want to decode an array element,
          # so remove the leading comma.
          status = json.loads(msg[1:])
        except ValueError:
          print(msg, sep='', end='')
          sys.stdout.flush()
          continue

    if len(status) != 0 and len(custom_status) != 0:
      print(',', json.dumps(list(custom_status.values()) + add_plugins(status)), sep='')
      sys.stdout.flush()
    elif len(status) != 0:
      print(',', json.dumps(add_plugins(status)), sep='')
      sys.stdout.flush()

  pipe.close()
  os.unlink(pipe_path)

loop()
