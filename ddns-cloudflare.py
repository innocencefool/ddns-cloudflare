#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import http.client
import json
import logging
import os
import socket

# permission needed: #zone:read #dns_records:edit
API_TOKEN = '########################################'
ZONE = 'cloudflare.com'
RECORD = 'api'

DOMAIN = '%s.%s' % (RECORD, ZONE)

DDNS_CONF = os.path.split(os.path.realpath(__file__))[0] + os.sep + 'ddns-cloudflare.conf'
DDNS_LOG = os.path.split(os.path.realpath(__file__))[0] + os.sep + 'ddns-cloudflare.log'


def restful_api(url, method='GET', data=None):
    try:
        headers = {'Authorization': 'Bearer %s' % API_TOKEN, 'Content-Type': 'application/json'}
        connection = http.client.HTTPSConnection(host='api.cloudflare.com', timeout=10)
        if data is not None:
            logging.info('%s %s %s' % (method, url, data))
            connection.request(method, url, json.dumps(data), headers)
        else:
            logging.info('%s %s' % (method, url))
            connection.request(method, url, headers=headers)
        response = connection.getresponse()
        logging.info('%s %s' % (response.status, response.reason))
        result = json.loads(response.read().decode('utf-8'))
        connection.close()
        if result['errors'] is not None and len(result['errors']) > 0 \
                and result['errors'][0]['message'] is not None:
            logging.error(result['errors'][0]['message'])
        return result['result']
    except Exception as e:
        logging.error(e)


def list_zones():
    url = '/client/v4/zones?name=%s' % ZONE
    result = restful_api(url)
    number = 0
    if result is not None:
        number = len(result)
    if number == 1:
        return result[0]['id']
    else:
        logging.error('List Zones %s' % number)


def list_records(zone_id):
    record_id = None
    url = '/client/v4/zones/%s/dns_records?name=%s' % (zone_id, DOMAIN)
    result = restful_api(url)
    if result is not None and len(result) > 0:
        for record in result:
            if record['type'] == 'CNAME':
                delete_record(zone_id, record['id'])
            elif record['type'] == 'AAAA':
                if record_id is not None:
                    delete_record(zone_id, record['id'])
                else:
                    record_id = record['id']
    return record_id


def delete_record(zone_id, record_id):
    url = '/client/v4/zones/%s/dns_records/%s' % (zone_id, record_id)
    restful_api(url, 'DELETE')


def create_record(zone_id, content):
    url = '/client/v4/zones/%s/dns_records' % zone_id
    data = {'type': 'AAAA', 'name': DOMAIN, 'content': content, 'ttl': 120, 'proxied': False}
    result = restful_api(url, 'POST', data)
    if result is not None:
        return result['id']


def update_record(zone_id, record_id, content):
    url = '/client/v4/zones/%s/dns_records/%s' % (zone_id, record_id)
    data = {'type': 'AAAA', 'name': DOMAIN, 'content': content, 'ttl': 120, 'proxied': False}
    result = restful_api(url, 'PUT', data)
    if result is not None:
        return result['id']


def get_recorded():
    try:
        client = socket.getaddrinfo(DOMAIN, 3389)
        return client[0][4][0]
    except Exception as e:
        logging.error(e)


def get_expected():
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as client:
            client.connect(('2400:3200::1', 53))
            return client.getsockname()[0]
    except Exception as e:
        logging.error(e)


def load_conf():
    try:
        if os.path.exists(DDNS_CONF):
            with open(DDNS_CONF, 'r') as ddns_conf:
                dict_conf = json.load(ddns_conf)
                if dict_conf.get('domain') is not None and dict_conf.get('domain') == DOMAIN:
                    return dict_conf.get('zone_id'), dict_conf.get('record_id')
        return None, None
    except Exception as e:
        logging.error(e)
        return None, None


def save_conf(zone_id=None, record_id=None):
    try:
        dict_conf = {'domain': DOMAIN, 'zone_id': zone_id, 'record_id': record_id}
        with open(DDNS_CONF, 'w') as ddns_conf:
            json.dump(dict_conf, ddns_conf)
    except Exception as e:
        logging.error(e)


def clear_conf():
    save_conf()


def main():
    expected = get_expected()
    if expected is not None:
        recorded = get_recorded()
        if recorded is None or recorded != expected:
            zone_id, record_id = load_conf()
            if zone_id is None or record_id is None:
                zone_id = list_zones()
                if zone_id is not None:
                    record_id = list_records(zone_id)
                    if record_id is not None:
                        save_conf(zone_id, record_id)
            if zone_id is not None:
                if record_id is None:
                    record_id = create_record(zone_id, expected)
                    if record_id is not None:
                        save_conf(zone_id, record_id)
                elif update_record(zone_id, record_id, expected) is None:
                    clear_conf()


if __name__ == '__main__':
    logging.basicConfig(filename=DDNS_LOG, format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
    main()
