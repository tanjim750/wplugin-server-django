import requests
import json
from datetime import datetime

login_user = {
    'session': None, # request login session
    'token': ''
}
class RedxAPI:
    def __init__(self, api_token=None, test_mode=True,username=None,password=None):
        self.api_token = api_token
        self.username = username
        self.password = password
        self.base_url = 'https://sandbox.redx.com.bd/v1.0.0-beta' if test_mode else 'https://openapi.redx.com.bd/v1.0.0-beta'

    
    def login(self):
        """Login and store session + token."""
        login_url = "https://api.redx.com.bd/v4/auth/login"
        payload = {
            "phone": self.username,
            "password": self.password
        }
        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": "https://redx.com.bd",
            "referer": "https://redx.com.bd/",
            "user-agent": "Mozilla/5.0"
        }

        session = requests.Session()
        resp = session.post(login_url, json=payload, headers=headers)

        if resp.status_code == 200:
            data = resp.json()
            token = data["data"]["accessToken"]
            login_user['session'] = session
            login_user['token'] = token
            print("[INFO] Redx Login successful")
            return True
        else:
            print("[ERROR] Redx Login failed:", resp.text)
            return False

    def courier_ratio(self, phone_number):
        """Get customer-success-return-rate, retry login if unauthorized."""
        if not login_user['session'] or not login_user['token']:
            print("[INFO] Redx No active session, logging in...")
            if not self.login():
                return {
                "total_parcel": 0,
                "success_parcel": 0,
                "cancelled_parcel": 0,
                "success_ratio": 0
            }

        url = "https://redx.com.bd/api/redx_se/admin/parcel/customer-success-return-rate"
        params = {"phoneNumber": phone_number}
        headers = {
            "accept": "application/json, text/plain, */*",
            "user-agent": "Mozilla/5.0",
            "referer": "https://redx.com.bd/create-parcel/",
            "x-access-token": f"Bearer {login_user['token']}"
        }

        resp = login_user['session'].get(url, headers=headers, params=params)
        print("[info] redx",resp.json())
        if resp.status_code == 401:
            print("[WARN] Session expired, re-logging in...")
            if self.login():
                return self.courier_ratio(phone_number)
            else:
                return {
                "total_parcel": 0,
                "success_parcel": 0,
                "cancelled_parcel": 0,
                "success_ratio": 0
            }

        if resp.status_code == 200:
            data = resp.json().get("data", {})
            # Convert string numbers to integers
            total_parcel = int(data.get("totalParcels", "0"))
            success_parcel = int(data.get("deliveredParcels", "0"))
            cancelled_parcel = total_parcel - success_parcel
            try:
                success_ratio = round((success_parcel / total_parcel) * 100, 2) if total_parcel > 0 else 0
            except ZeroDivisionError:
                success_ratio = 0

            # Return in required format
            return {
                "total_parcel": total_parcel,
                "success_parcel": success_parcel,
                "cancelled_parcel": cancelled_parcel,
                "success_ratio": success_ratio
            }
        else:
            print("[ERROR] Redx Failed to get courier ratio.")
            return {
                "total_parcel": 0,
                "success_parcel": 0,
                "cancelled_parcel": 0,
                "success_ratio": 0
            }


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
            'delivery_area': customer_address,
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
            print(response.json())
            response.raise_for_status()
            body = response.json()

            if 'tracking_id' in body:
                # Save tracking_id to your order meta in actual use
                return {'success': True, 'tracking_id': body['tracking_id'],'message':'Order Created Successfully'}
            else:
                return {'success': False, 'error': body, 'sent_data': data}
            # return body

        except requests.RequestException as e:
            print(e)
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
