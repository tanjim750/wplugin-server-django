from datetime import datetime

import requests


class PathaoApi(object):
    '''
        A few norms of the pathao api that's not mentioned in the api DOCs
        :item_type can be any value {1, 2, 3} represents {Document, Parcel, Fragile} as far as my understanding goes
        :access_tokens has a expiration time, so it's need to be regenerated if one expires
    '''

    def __init__(self, client_id, client_secret, username, password, base_url=None):
        self.base_url = base_url or 'https://api-hermes.pathao.com'
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.issued_access_token_response = None
        self.issue_access_token_timestamp = None
        self.headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}

    def issue_access_token(self):
        url = f'{self.base_url}/aladdin/api/v1/issue-token'
        data = {'client_id': self.client_id,
                'client_secret': self.client_secret,
                'username': self.username,
                'password': self.password,
                'grant_type': "password",
                }
        response = requests.post(url, json=data, headers=self.headers)
        self.issued_access_token_response = response.json()
        self.issue_access_token_timestamp = datetime.timestamp(datetime.now())
        return response.json()

    @property
    def access_token(self):
        if not self.issued_access_token_response:
            self.issue_access_token()
        timestamp_now = datetime.timestamp(datetime.now())
        if (timestamp_now - self.issue_access_token_timestamp) > self.issued_access_token_response['expires_in']:
            self.issue_access_token()
        return self.issued_access_token_response['access_token']

    @property
    def auth_headers(self):
        headers = self.headers
        headers.update({'Authorization': 'Bearer %s' % self.access_token})
        return headers

    def get_response_data(self, url, data=None, method='get', headers=None):
        response = None
        if method == 'get':
            response = requests.get(url, headers=headers or self.headers)
        if method == 'post':
            response = requests.post(url, json=data, headers=headers or self.auth_headers)
        return response.json()['data']

    def get_city_list(self):
        url = f'{self.base_url}/aladdin/api/v1/countries/1/city-list'
        return self.get_response_data(url)

    def get_zone_list(self, city_id):
        url = f'{self.base_url}/aladdin/api/v1/cities/{city_id}/zone-list'
        return self.get_response_data(url)

    def get_area_list(self, zone_id):
        url = f'{self.base_url}/aladdin/api/v1/zones/{zone_id}/area-list'
        return self.get_response_data(url)

    def create_order(self, store_id, order_id, sender_name, sender_phone, recipient_name, recipient_phone, address,
                     city_id, zone_id, area_id, special_instruction, item_quantity, item_weight, amount_to_collect,
                     item_description, delivery_type=48, item_type='2'):
        url = f'{self.base_url}/aladdin/api/v1/orders'
        data = {
            'store_id': store_id,
            'merchant_order_id': str(order_id),
            'sender_name': sender_name,
            'sender_phone': sender_phone,
            'recipient_name': recipient_name,
            'recipient_phone': recipient_phone,
            'recipient_address': address,
            'recipient_city': city_id,
            'recipient_zone': zone_id,
            'recipient_area': area_id,
            'delivery_type': delivery_type,
            'item_type': item_type,
            'special_instruction': special_instruction,
            'item_quantity': item_quantity,
            'item_weight': item_weight,
            'amount_to_collect': amount_to_collect,
            'item_description': item_description,
        }
        data = self.get_response_data(url=url, data=data, method='post', headers=self.auth_headers)
        return data

    def get_delivery_cost(self, store_id, city_id, zone_id, item_type='2', delivery_type=48, item_weight=.5):
        url = f'{self.base_url}/aladdin/api/v1/merchant/price-plan'
        data = {'store_id': store_id,
                'item_type': item_type,
                'delivery_type': delivery_type,
                'item_weight': item_weight,
                'recipient_city': city_id,
                'recipient_zone': zone_id}
        data = self.get_response_data(url, data=data, method='post', headers=self.auth_headers)
        return data

    def get_stores(self):
        url = f'{self.base_url}/aladdin/api/v1/stores'
        response = requests.get(url, headers=self.auth_headers)
        return response.json()
