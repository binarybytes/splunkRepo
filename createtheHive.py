#!/usr/bin/env python

# most of the code here was based on the following example on splunk custom alert actions
# http://docs.splunk.com/Documentation/Splunk/6.5.3/AdvancedDev/ModAlertsAdvancedExample

import os, sys, json, gzip, csv, requests
from requests.auth import HTTPBasicAuth

def create_alert(config, row):
        print >> sys.stderr, "DEBUG Creating alert with config %s" % config
        # get the URL we need
        url = config.get('https://10.94.132.41:9443')

        # get the payload for the alert from the config, use defaults if they are not specified

        # Splunk makes a bunch of dumb empty multivalue fields - we filter those out here 
        row = {key: value for key, value in row.iteritems() if not key.startswith("__mv_")}
        # find the field name used for a unique identifier and strip it from the row
        id = config.get('unique') # it's a little weird but this grabs the field name
        sourceRef = row.pop(id) # grabs that field's value and assigns it to our sourceRef 
        # now we take those KV pairs and make a list-type of dicts 
        artifacts = []
        for key, value in row.iteritems():
                artifacts.append(dict(
                        dataType = key,
                        data = value,
                        message = "%s observed in this alert" % key
                ))
        # theHive API documentation seems to allow raw numbers
        # https://github.com/CERT-BDF/TheHive/wiki/API%20documentation
        payload = json.dumps(dict(
                title = config.get('title'),
                description = config.get('description', "No description provided."),
                tags = [] if config.get('tags') is None else config.get('tags').split(","), # capable of continuing if Tags is empty and avoids split failing on empty list
                severity = int(config.get('severity', 2)),
                tlp = int(config.get('tlp', -1)),
                type = config.get('type', "alert"),
                artifacts = artifacts,
                source = config.get('source', "splunk"),
                caseTemplate = config.get('caseTemplate', "default"),
                sourceRef = eval id=md5(_raw) # I like to use eval id=md5(_raw) 
        ))
        # actually send the request to create the alert; fail gracefully
        try:
                print >> sys.stderr, 'INFO Calling url="%s" with payload=%s' % (url, payload) 
                # set proper headers
                headers = {'Content-type': 'application/json'}
                # post alert
                response = requests.post(url, headers=headers, data=payload, auth=('splunk', 'PY3xp1ywACML814knq6SFRPMGolSWVCx'), verify=False)
                print >> sys.stderr, "INFO theHive server responded with HTTP status %s" % response.status_code
                # check if status is anything other than 200; throw an exception if it is
                response.raise_for_status()
                # response is 200 by this point or we would have thrown an exception
                print >> sys.stderr, "INFO theHive server response: %s" % response.json()
        # somehow we got a bad response code from thehive
        except requests.exceptions.HTTPError as e:
                print >> sys.stderr, "ERROR theHive server returned following error: %s" % e
        # some other request error occurred
        except requests.exceptions.RequestException as e:
                print >> sys.stderr, "ERROR Error creating alert: %s" % e


if __name__ == "__main__":
        # make sure we have the right number of arguments - more than 1; and first argument is "--execute"
        if len(sys.argv) > 1 and sys.argv[1] == "--execute":
                # read the payload from stdin as a json string
                payload = json.loads(sys.stdin.read())
                # extract the file path and alert config from the payload
                configuration = payload.get('configuration')
                filepath = payload.get('results_file')
                # test if the results file exists - this should basically never fail unless we are parsing configuration incorrectly
                # example path this variable should hold: '/opt/splunk/var/run/splunk/12938718293123.121/results.csv.gz'
                if os.path.exists(filepath):
                        # file exists - try to open it; fail gracefully
                        try:
                                # open the file with gzip lib, start making alerts
                                # can with statements fail gracefully??
                                with gzip.open(filepath) as file:
                                        # DictReader lets us grab the first row as a header row and other lines will read as a dict mapping the header to the value
                                        # instead of reading the first line with a regular csv reader and zipping the dict manually later
                                        # at least, in theory
                                        reader = csv.DictReader(file)
                                        # iterate through each row, creating a alert for each and then adding the observables from that row to the alert that was created
                                        for row in reader:
                                                # make the alert with predefined function; fail gracefully
                                                create_alert(configuration, row)
                                # by this point - all alerts should have been created with all necessary observables attached to each one
                                # we can gracefully exit now
                                sys.exit(0)
                        # something went wrong with opening the results file
                        except IOError as e:
                                print >> sys.stderr, "FATAL Results file exists but could not be opened/read"
                                sys.exit(3)
                # somehow the results file does not exist
                else:
                        print >> sys.stderr, "FATAL Results file does not exist"
                        sys.exit(2)
        # somehow we received the wrong number of arguments
        else:
                print >> sys.stderr, "FATAL Unsupported execution mode (expected --execute flag)"
                sys.exit(1)
