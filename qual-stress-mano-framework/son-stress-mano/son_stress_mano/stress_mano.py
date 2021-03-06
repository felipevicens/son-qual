"""
Copyright (c) 2015 SONATA-NFV
ALL RIGHTS RESERVED.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
nor the names of its contributors may be used to endorse or promote
products derived from this software without specific prior written
permission.
This work has been performed in the framework of the SONATA project,
funded by the European Commission under Grant number 671517 through
the Horizon 2020 and 5G-PPP programmes. The authors would like to
acknowledge the contributions of their colleagues of the SONATA
partner consortium (www.sonata-nfv.eu).a
"""

import logging
import yaml
import time
import os
import requests
import copy
import uuid
import json
import threading
import sys
import concurrent.futures as pool
# import psutil

from sonmanobase.plugin import ManoBasePlugin

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("plugin:stress_mano")
LOG.setLevel(logging.INFO)

GK_CREATE = "service.instances.create"
GK_TERM = "service.instance.terminate"


class StressMano(ManoBasePlugin):
    """
    This class implements the Function lifecycle manager.
    """

    def __init__(self,
                 auto_register=True,
                 wait_for_registration=True,
                 start_running=True):
        """
        Initialize class and son-mano-base.plugin.BasePlugin class.
        This will automatically connect to the broker, contact the
        plugin manager, and self-register this plugin to the plugin
        manager.

        After the connection and registration procedures are done, the
        'on_lifecycle_start' method is called.
        :return:
        """

        ver = "0.1-dev"
        des = "This is the stress mano plugin"

        self.results = {}
        self.vnfs_to_test = list(map(int, os.environ.get("amount_of_vnfs")[1:-1].split(',')))
        LOG.info(str(self.vnfs_to_test))
        self.reproduce = int(os.environ.get("reproduce"))
        self.amount_of_requests = list(map(int, os.environ.get("amount_of_requests")[1:-1].split(',')))

        self.playbook = []
        self.resultbook = []

        for vnf in self.vnfs_to_test:
            for amount in self.amount_of_requests:
                self.playbook.append({'vnf': vnf, 'rep': self.reproduce, 'amount': amount, 'start_times': [], 'stop_times': []})


        super(self.__class__, self).__init__(version=ver,
                                             description=des,
                                             auto_register=auto_register,
                                             wait_for_registration=wait_for_registration,
                                             start_running=start_running)

    def __del__(self):
        """
        Destroy plugin instance. De-register. Disconnect.
        :return:
        """
        super(self.__class__, self).__del__()

    def declare_subscriptions(self):
        """
        Declare topics that Plugin subscribes on.
        """
        # We have to call our super class here
        super(self.__class__, self).declare_subscriptions()

        # The topic on which deploy requests are posted.
        # topic = 'mano.service.place'
        # self.manoconn.subscribe(self.placement_request, topic)

        # subscribe to create and terminate topics
        self.manoconn.subscribe(self.create_message_received, GK_CREATE)
        self.manoconn.subscribe(self.term_message_received, GK_TERM)
        self.manoconn.subscribe(self.test, 'infrastructure.function.deploy')

        LOG.info("Subscribed to topic: ")

    def on_lifecycle_start(self, ch, mthd, prop, msg):
        """
        This event is called when the plugin has successfully registered itself
        to the plugin manager and received its lifecycle.start event from the
        plugin manager. The plugin is expected to do its work after this event.

        :param ch: RabbitMQ channel
        :param method: RabbitMQ method
        :param properties: RabbitMQ properties
        :param message: RabbitMQ message content
        :return:
        """
        super(self.__class__, self).on_lifecycle_start(ch, mthd, prop, msg)
        LOG.info("Stress Mano plugin started and operational.")

        self.start_next_test()

    def deregister(self):
        """
        Send a deregister request to the plugin manager.
        """
        LOG.info('Deregistering stress mano plugin with uuid ' + str(self.uuid))
        message = {"uuid": self.uuid}
        self.manoconn.notify("platform.management.plugin.deregister",
                             json.dumps(message))
        os._exit(0)

    def on_registration_ok(self):
        """
        This method is called when the Stress Mano plugin
        is registered to the plugin mananger
        """
        super(self.__class__, self).on_registration_ok()
        LOG.debug("Received registration ok event.")

    def test(self, ch, method, prop, payload):
        LOG.info("IA DEPLOY")
        LOG.info(payload)

    def create_message_received(self, ch, method, prop, payload):

        timestamp = time.time()
        if prop.app_id != self.name:
            message = yaml.load(payload)
            LOG.info(payload)
            if message['status'] == 'READY':
                LOG.info("request finished.")
                self.playbook[0]['stop_times'].append(timestamp)

                if len(self.playbook[0]['stop_times']) == self.playbook[0]['amount']:
                    LOG.info('all tests in sequence done, starting next set.')
                    self.resultbook.append(self.playbook.pop(0))
                    self.start_next_test()                

    def term_message_received(self, ch, method, prop, payload):
        pass

    def start_next_test(self):

        if len(self.playbook) > 0:
            setup = self.playbook[0]
            LOG.info('new test starting: amount of vnfs: ' + str(setup['vnf']) + ', times repeated: ' + str(setup['rep']) + ', amount of requests: ' + str(setup['amount']))
            for i in range(setup['amount']):
                payload = self.create_request(vnf=setup['vnf'])
                corr_id = str(uuid.uuid4())
                timestamp = time.time()
                self.manoconn.notify(GK_CREATE, yaml.dump(payload), correlation_id=corr_id)
                self.playbook[0]['start_times'].append(timestamp)
                LOG.info("request sent.")
        else:
            LOG.info("All tests are finished")
            LOG.info(str(self.resultbook))

    def create_request(self, vnf=2):

        request = {}

        nsd = yaml.load(open('descriptors/nsd.yml'))

        net_func = []

        for i in range(vnf):
            LOG.info('adding vnf to nsd')
            new_vnf = {}
            new_vnf['vnf_id'] = "vnf_" + str(i+1)
            new_vnf['vnf_vendor'] = "eu.sonata-nfv"
            new_vnf["vnf_name"] = "vnf-" + str(i+1)
            new_vnf["vnf_version"] = "0.1"
            net_func.append(new_vnf)

        nsd["network_functions"] = net_func
        nsd['uuid'] = str(uuid.uuid4())

        new_vl = []
        for i in range(1, vnf + 1):
            new_vl.append("vnf_" + str(i) + ':mgmt')

        nsd['virtual_links'][0]['connection_points_reference'] = new_vl

        nsd['forwarding_graphs'][0]['number_of_virtual_links'] = 1
        new = [{'connection_point_ref': 'input', 'position': 1},{'connection_point_ref': 'vnf_1:input', 'position': 2}]
        nsd['forwarding_graphs'][0]['network_forwarding_paths'][0]['connection_points'] = new

        request['NSD'] = nsd

        for i in range(1, vnf + 1):
            vnfd = yaml.load(open('descriptors/vnfd.yml'))
            vnfd['uuid'] = nsd['uuid'] = str(uuid.uuid4())
            vnfd['name'] = 'vnf-' + str(i)
            request['VNFD' + str(i)] = vnfd

        LOG.info(yaml.dump(request))
        return request


def main():
    """
    Entry point to start plugin.
    :return:
    """
    # reduce messaging log level to have a nicer output for this plugin
    logging.getLogger("son-mano-base:messaging").setLevel(logging.INFO)
    logging.getLogger("son-mano-base:plugin").setLevel(logging.INFO)
#    logging.getLogger("amqp-storm").setLevel(logging.DEBUG)
    # create our function lifecycle manager
    stress_mano = StressMano()

if __name__ == '__main__':
    main()
