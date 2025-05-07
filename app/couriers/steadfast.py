import requests
from urllib.parse import urlencode
from datetime import datetime

import traceback

class SteadFastAPI:
    def __init__(self, api_key, secret_key):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = 'https://portal.packzy.com/api/v1'

    def create_parcel(self, order):
        if not order:
            return {'success': False, 'error': 'Invalid order reaquest.'}

        recipient_name = order['billing'].get('first_name', '') + ' ' + order['billing'].get('last_name', '')
        recipient_phone = order['billing'].get('phone', '')
        recipient_address = order['billing'].get('address_1', '')

        merchant_invoice_id = str(order.get('id', ''))
        cash_collection_amount = float(order.get('total', 0))
        

        url = f"{self.base_url}/create_order"
        headers = {
            'Api-Key': self.api_key,
            'Secret-Key': self.secret_key,
            'Content-Type': 'application/json',
        }
        payload = {
            'invoice': merchant_invoice_id,
            'recipient_name': recipient_name,
            'recipient_phone': recipient_phone,
            'recipient_address': recipient_address,
            'cod_amount': cash_collection_amount,
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status') == 200:
                consignment = response_data.get('consignment')
                return {
                    'success': True,
                    'message': response_data.get('message', 'Order Created Successfully'),
                    'tracking_id': consignment.get('tracking_code')
                }

            error_message = response_data.get('message', 'Unknown error occurred.')
            if 'errors' in response_data:
                error_details = response_data['errors']
                error_message = ' '.join(
                    f"{key}: {', '.join(val)}" for key, val in error_details.items()
                )

            return {
                'success': False,
                'error': error_message,
                'http_code': response.status_code
            }

        except Exception as e:
            # traceback.print_exc()
            return {'success': False, 'error': f'Failed to create parcel. Try Again'}

    def track_parcel(self, tracking_code):
        url = f"https://steadfast.com.bd/track/consignment/{tracking_code}"

        try:
            response = requests.get(url)
            data = response.json()

            if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
                return {'success':False,'error': 'No tracking info found.'}

            tracking_updates = [
                 {
                    'desc':entry.get('text', ''),
                    'created_at':datetime.strptime(entry.get('created_at'), "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%b %-d, %Y %I:%M %p")
                 } for entry in data[1]
                ]
            return {
                'success':True,
                'status':self.convert_to_wp_status(tracking_updates[0]['desc']),
                'tracking': tracking_updates[::-1]
                }

        except requests.RequestException as e:
            return {'success':False, 'error': f'Request failed: {str(e)}'}
        except ValueError:
            return {'success':False, 'error': 'Invalid JSON response'}

    def get_parcel_status(self, tracking_code):
        url = f"{self.base_url}/status_by_trackingcode/{tracking_code}"
        headers = {
            'Api-Key': self.api_key,
            'Secret-Key': self.secret_key,
            'Content-Type': 'application/json',
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status') == 200:
                return {'success': True, 'status': self.convert_to_wp_status(response_data.get('delivery_status'))}

            return {
                'success': False,
                'error': response_data.get('message', 'Package not found.'),
                'http_code': response.status_code
            }

        except requests.RequestException as e:
            return {'success': False, 'error': "Invalid tracking id. Try again"}
    
    def convert_to_wp_status(self,status:str):
        if status.lower() == 'delivered' or 'delivered' in status.lower():
            return 'Completed'
        elif status.lower() == 'cancelled' or 'cancelled' in status.lower():
            return 'Cancelled'
        else:
            return 'Processing'
