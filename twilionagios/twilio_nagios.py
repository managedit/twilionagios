#!/usr/bin/python
import re
from syslog import syslog
from twisted.web.resource import Resource

HOST_STATE_MSG = {
  0: 'up',
  1: 'down',
  2: 'unreachable'
}
SERVICE_STATE_MSG = {
  0: 'ok',
  1: 'warning',
  2: 'critical',
  3: 'unknown'
}

class TwilioNagios(Resource):
  isLeaf = True

  def __init__(self, objects, status):
    self.objects = objects
    self.status = status

  def render(self, request):
    request.setHeader('Content-Type', 'text/xml')

    # Reload the nagios data files
    self.status_parsed = self.parse_status()
    self.objects_parsed = self.parse_objects()

    # Parse the request..
    try:
      action, hostname, service = request.postpath
    except (KeyError, ValueError):
      return '<Response/>'

    # Trigger the correct action
    if action == 'host':
      response = self.host(request, hostname)
    else if action == 'hostaction':
      response = self.hostaction(request, hostname)
    else if action == 'service':
      response = self.service(request, hostname, service)
    else if action == 'serviceaction':
      response = self.serviceaction(request, hostname, service)

    return response

  def hostalert(self, request, hostname):
    host_data = self.objects_parsed[('host', hostname)]
    status_data = self.status_parsed[('host', hostname)]
    state = int(status_data['current_state'])

    response = """
<Response>
  <Say>ALERT! Host %s is %s, I repeat, the host %s is %s</Say>
  <Gather action="/hostaction/%s/host" method="GET">
    <Say>Press 1 to acknowledge</Say>
    <Say>Press 2 to disable alerts for this host</Say>
  </Gather>
  <Say>We didn't receive any input. Goodbye!</Say>
</Response> """ % (hostname,
                   HOST_STATE_MSG[state],
                   hostname,
                   HOST_STATE_MSG[state],
                   hostname)

    return response

  def hostaction(self, request, hostname):
    response = """
<Response>
  <Say>This is a todo..</Say>
</Response> """

    return response

  def servicealert(self, request, hostname, service):
    host_data = self.objects_parsed[('host', hostname)]
    status_data = self.status_parsed[(service, hostname)]
    state = int(status_data['current_state'])

    response = """
<Response>
  <Say>ALERT! Service %s on host %s is %s, I repeat, Service %s on host %s is %s</Say>
  <Gather action="/serviceaction/%s/%s" method="GET">
    <Say>Press 1 to acknowledge</Say>
    <Say>Press 2 to disable alerts for this service</Say>
  </Gather>
  <Say>We didn't receive any input. Goodbye!</Say>
</Response> """ % (service,
                   hostname,
                   SERVICE_STATE_MSG[state],
                   service,
                   hostname,
                   SERVICE_STATE_MSG[state],
                   hostname,
                   service)

    return response

  def serviceaction(self, request, hostname, service):
    response = """
<Response>
  <Say>This is a todo..</Say>
</Response> """

  def parse_objects(self):
    filename = self.objects
    conf = []
    f = open(filename, 'r')
    for i in f.readlines():
        if i[0] == '#': continue
        matchID = re.search(r"define ([\w]+) {", i)
        matchAttr = re.search(r"[ ]*([\w]+)\s+(.*)$", i)
        matchEndID = re.search(r"[ ]*}", i)
        if matchID:
            identifier = matchID.group(1)
            cur = [identifier, {}]
        elif matchAttr:
            attribute = matchAttr.group(1)
            value = matchAttr.group(2)
            cur[1][attribute] = value
        elif matchEndID:
            conf.append(cur)
    new_conf = {}
    for entry in conf:
      if entry[0] == 'host':
        new_conf[('host', entry[1]['host_name'])] = entry[1]
      elif entry[0] == 'service':
        new_conf[(entry[1]['service_description'], entry[1]['host_name'])] = entry[1]
    return new_conf

  def parse_status(self):
    filename = self.status
    conf = []
    f = open(filename, 'r')
    for i in f.readlines():
        if i[0] == '#': continue
        matchID = re.search(r"([\w]+) {", i)
        matchAttr = re.search(r"[ ]*([\w]+)=(.*)", i)
        matchEndID = re.search(r"[ ]*}", i)
        if matchID:
            identifier = matchID.group(1)
            cur = [identifier, {}]
        elif matchAttr:
            attribute = matchAttr.group(1)
            value = matchAttr.group(2)
            cur[1][attribute] = value
        elif matchEndID:
            conf.append(cur)
    new_conf = {}
    for entry in conf:
      if entry[0] == 'hoststatus':
        new_conf[('host', entry[1]['host_name'])] = entry[1]
      elif entry[0] == 'servicestatus':
        new_conf[(entry[1]['service_description'], entry[1]['host_name'])] = entry[1]
    return new_conf