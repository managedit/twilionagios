#!/usr/bin/python
import re
import urllib
import sys
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

  def __init__(self, objects_file, status_file, external_file):
    self.objects = objects_file
    self.status = status_file
    self.external = external_file

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
      response = self.hostalert(request, hostname)
    elif action == 'hostaction':
      response = self.hostaction(request, hostname)
    elif action == 'service':
      response = self.servicealert(request, hostname, service)
    elif action == 'serviceaction':
      response = self.serviceaction(request, hostname, service)

    return response

  def hostalert(self, request, hostname):
    host_data = self.objects_parsed[('host', hostname)]
    status_data = self.status_parsed[('host', hostname)]
    state = int(status_data['current_state'])

    response = """
<Response>
  <Say>ALERT! Host %s is %s, I repeat, the host %s is %s</Say>
  <Gather action="/hostaction/%s/host" method="GET" numDigits="1">
    <Say>Press 1 to acknowledge</Say>
    <Say>Press 2 to disable alerts for this host</Say>
  </Gather>
  <Say>We didn't receive any input. Goodbye!</Say>
</Response> """ % (hostname,
                   HOST_STATE_MSG[state],
                   hostname,
                   HOST_STATE_MSG[state],
                   urllib.quote_plus(hostname))

    return response

  def hostaction(self, request, hostname):
    digit = int(request.args['Digits'][0])

    if digit == 1:
      # Acknowledge Service Issue
      response = """
<Response>
  <Say>Acknowledging this service issue. Goodbye!</Say>
</Response> """

      with open(self.external, "w") as f:
        f.write("[0] ACKNOWLEDGE_HOST_PROBLEM;%s;1;1;1;Twilio;Ackd via Twilio\n" % (hostname))

    elif digit == 2:
      # Disable Host Alerts
      response = """
<Response>
  <Say>Disabling alerts for this host. Goodbye!</Say>
</Response> """

      with open(self.external, "w") as f:
        f.write("[0] DISABLE_HOST_NOTIFICATIONS;%s\n" % (hostname))

    else:
      response = """
<Response>
  <Say>Invalid choice.</Say>
  <Redirect method="GET">/host/%s/host</Redirect>
</Response> """ % (urllib.quote_plus(hostname))

    return response

  def servicealert(self, request, hostname, service):
    host_data = self.objects_parsed[('host', hostname)]
    status_data = self.status_parsed[(service, hostname)]
    state = int(status_data['current_state'])

    response = """
<Response>
  <Say>ALERT! Service %s on host %s is %s, I repeat, Service %s on host %s is %s</Say>
  <Gather action="/serviceaction/%s/%s" method="GET" numDigits="1">
    <Say>Press 1 to acknowledge this service issue</Say>
    <Say>Press 2 to disable alerts for this service</Say>
  </Gather>
  <Say>We didn't receive any input. Goodbye!</Say>
</Response> """ % (service,
                   hostname,
                   SERVICE_STATE_MSG[state],
                   service,
                   hostname,
                   SERVICE_STATE_MSG[state],
                   urllib.quote_plus(hostname),
                   urllib.quote_plus(service))

    return response

  def serviceaction(self, request, hostname, service):
    digit = int(request.args['Digits'][0])

    if digit == 1:
      # Acknowledge Service Issue
      response = """
<Response>
  <Say>Acknowledging this service issue. Goodbye!</Say>
</Response> """

      with open(self.external, "w") as f:
        f.write("[0] ACKNOWLEDGE_SVC_PROBLEM;%s;%s;1;1;1;Twilio;Ackd via Twilio\n" % (hostname, service))

    elif digit == 2:
      # Disable Service Alerts
      response = """
<Response>
  <Say>Disabling alerts for this service. Goodbye!</Say>
</Response> """

      with open(self.external, "w") as f:
        f.write("[0] DISABLE_SVC_NOTIFICATIONS;%s;%s\n" % (hostname, service))

    else:
      response = """
<Response>
  <Say>Invalid choice.</Say>
  <Redirect method="GET">/host/%s/%s</Redirect>
</Response> """ % (urllib.quote_plus(hostname),
                   urllib.quote_plus(service))

    return response

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