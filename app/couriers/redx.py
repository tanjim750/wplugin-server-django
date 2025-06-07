import requests
import json
from datetime import datetime

class RedxAPI:
    def __init__(self, api_token, test_mode=True):
        self.api_token = api_token
        self.base_url = 'https://sandbox.redx.com.bd/v1.0.0-beta' if test_mode else 'https://openapi.redx.com.bd/v1.0.0-beta'

    def create_parcel(self, order):
        if not order:
            return {'success': False, 'message': 'Invalid order'}

        customer_name = order['billing'].get('first_name', '') + ' ' + order['billing'].get('last_name', '')
        customer_phone = order['billing'].get('phone', '')
        customer_address = order['billing'].get('address_1', '')

        # Optional fallback logic to derive delivery area and ID (e.g., from state)
        delivery_area = order['billing'].get('state', '')  # You can replace this with logic to convert state to area name
        delivery_area_id = 1  # Example static mapping for 'BD-13' or look up dynamically

        merchant_invoice_id = str(order.get('id', ''))
        cash_collection_amount = float(order.get('total', 0))
        parcel_weight = 1.0  # Assign default or calculate from product data
        value = float(order.get('total', 0))

        items = order.get('items', [])
        parcel_details = []

        for item in items:
            parcel_details.append({
                'name': item.get('name'),
                'category': 'general',
                'value': int(float(item.get('total', 0)))
            })

        data = {
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'delivery_area': delivery_area,
            'delivery_area_id': delivery_area_id,  # Static, should be mapped properly
            'customer_address': customer_address,
            'merchant_invoice_id': merchant_invoice_id,
            'cash_collection_amount': cash_collection_amount,
            'parcel_weight': parcel_weight,
            'instruction': '',
            'value': value,
            'is_closed_box': True,
            'parcel_details_json': parcel_details
        }

        headers = {
            'Content-Type': 'application/json',
            'API-ACCESS-TOKEN': f"Bearer {self.api_token}",
        }

        try:
            response = requests.post(f"{self.base_url}/parcel", headers=headers, json=data, timeout=20)
            # print(response.json())
            response.raise_for_status()
            body = response.json()

            if 'tracking_id' in body:
                # Save tracking_id to your order meta in actual use
                return {'success': True, 'tracking_id': body['tracking_id'],'message':'Order Created Successfully'}
            else:
                return {'success': False, 'error': body, 'sent_data': data}
            # return body

        except requests.RequestException as e:
            return {'success': False, 'error': f"Invalid data. Please try again."}

    def track_parcel(self, tracking_id):
        headers = {
            'Content-Type': 'application/json',
            'API-ACCESS-TOKEN': f"Bearer {self.api_token}",
        }

        try:
            response = requests.get(f"{self.base_url}/parcel/track/{tracking_id}", headers=headers, timeout=20)
            # response.raise_for_status()
            data = response.json()
            if data.get('tracking',False):
                tracking = []
                for t in data['tracking']:
                    tracking.append(
                        {
                            'desc':t['message_en'],
                            'created_at': datetime.strptime(t.get('time'), "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%b %-d, %Y %I:%M %p")
                        }
                    )
                
                return {
                    'success': True,
                    'status': self.convert_to_wp_status(tracking[-1]['desc']),
                    'tracking': tracking
                }
            else:
                return {
                    'success':False,
                    'error': 'No tracking info found.'
                }
        except requests.RequestException as e:
            return {'success':False,'error': "Something went wrong. Try again."}

    def convert_to_wp_status(self,status:str):
        if status.lower() == 'delivered' or 'delivered' in status.lower():
            return 'Completed'
        elif status.lower() == 'cancelled' or 'cancelled' in status.lower():
            return 'Cancelled'
        elif status.lower() == 'return' or 'return' in status.lower():
            return 'Refunded'
        else:
            return 'Processing'
