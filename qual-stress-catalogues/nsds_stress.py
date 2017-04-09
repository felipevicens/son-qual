#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""nsds stress tests"""

# Work in progress...

import requests
import uuid
import yaml
import time
import sys, os
from stress_test import StressTest

TARGET = 'http://sp.int3.sonata-nfv.eu'
DESCRIPTOR_SAMPLE = 'qual-stress-catalogues/resources/nsd.yml'

class TestNsd(StressTest):
    """nsd class"""

    def __init__(self, ntests, target, sample=DESCRIPTOR_SAMPLE):
        super(TestNsd, self).__init__(ntests, target)
        self._target = target
        self._entries = []
        self._sample = sample

    def populate(self):
        for i in range(0,self._ntests):
            with open(self._sample, 'r') as stream:
                descriptor = yaml.load(stream)
                descriptor['vendor'] = str(uuid.uuid4())
                descriptor['name'] = str(uuid.uuid4())
                descriptor['version'] = str(uuid.uuid4())
            self._entries.append(descriptor)

    def send(self):
        """Sends descriptor"""
        url = '{0}:4002/catalogues//api/v2/network-services'.format(self._target)
        headers = {'Content-Type': 'application/x-yaml'}
        try:
            resp = requests.post(url, data=yaml.dump(self._entries.pop()), headers=headers)
            if not resp.status_code in (200,201):
                print 'Error {0}'.format(resp.status_code)
                os._exit(1)
        except Exception as exc:
            print 'Error {0}'.format(exc)
            os._exit(1)


if __name__ == '__main__':

    if len(sys.argv) > 1:
        TARGET = sys.argv[1]
    print 'Nsd stress test'
    limits = [10, 100, 1000]
    for limit in limits:
        test = TestNsd(limit, TARGET)
        test.run()
