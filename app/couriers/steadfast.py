import requests
from urllib.parse import urlencode
from datetime import datetime
from bs4 import BeautifulSoup
import traceback


login_user = {
    'session': None,  # store logged-in session
    'logged_in': False
}

class SteadFastAPI:
    def __init__(self, api_key=None, secret_key=None,email=None,password=None):
        self.api_key = api_key
        self.secret_key = secret_key
        self.email = email
        self.password = password
        self.base_url = 'https://portal.packzy.com/api/v1'

    def login(self):
        """Login to Steadfast and store session."""
        try:
            session = requests.Session()

            # 1. Get login page
            login_page = session.get(f"https://steadfast.com.bd/login")
            soup = BeautifulSoup(login_page.text, "html.parser")

            # 2. Extract CSRF token
            token_tag = soup.find("input", {"name": "_token"})
            if not token_tag:
                print("[ERROR] Steadfast Could not find CSRF token on login page.")
                return False
            token = token_tag["value"]

            # 3. Prepare payload
            payload = {
                "_token": token,
                "email": self.email,
                "password": self.password,
                "remember": "on"
            }

            # 4. Send login POST request
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/138.0.0.0 Safari/537.36",
                "Referer": f"https://steadfast.com.bd/login"
            }

            login_response = session.post(f"https://steadfast.com.bd/login", data=payload, headers=headers)

            if "dashboard" in login_response.url.lower():
                print("[INFO] Steadfast login successful.")
                login_user['session'] = session
                login_user['logged_in'] = True
                return True
            else:
                print("[ERROR] Steadfast Login failed. Check email/password.")
                return False

        except Exception as e:
            print(f"[ERROR] Steadfast Login exception: {e}")
            return False

    def courier_ratio(self, phone_number):
        """Get consignment data by phone number."""
        if not login_user['logged_in'] or not login_user['session']:
            print("[INFO] Steadfast No active session. Logging in...")
            if not self.login():
                return {
                "total_parcel": 0,
                "success_parcel": 0,
                "cancelled_parcel": 0,
                "success_ratio": 0
            }

        try:
            url = f"https://steadfast.com.bd/user/consignment/getbyphone/{phone_number}"
            resp = login_user['session'].get(url)

            if resp.status_code == 401:  # Session expired
                print("[WARN] Steadfast Session expired. Re-logging in...")
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
                data = resp.json()
                print("[INFO] steadfast",data)

                total_parcel = data.get("total_delivered", 0) + data.get("total_cancelled", 0)
                success_parcel = data.get("total_delivered", 0)
                cancelled_parcel = data.get("total_cancelled", 0)
                success_ratio = round((success_parcel / total_parcel) * 100, 2) if total_parcel > 0 else 0

                return {
                    "total_parcel": total_parcel,
                    "success_parcel": success_parcel,
                    "cancelled_parcel": cancelled_parcel,
                    "success_ratio": success_ratio
                }
            else:
                print(f"[ERROR] Steadfast Failed to fetch data. Status: {resp.status_code}")
                return {
                "total_parcel": 0,
                "success_parcel": 0,
                "cancelled_parcel": 0,
                "success_ratio": 0
            }

        except Exception as e:
            print(f"[ERROR] Steadfast Courier ratio exception: {e}")
            return {
                "total_parcel": 0,
                "success_parcel": 0,
                "cancelled_parcel": 0,
                "success_ratio": 0
            }

    def create_parcel(self, order):
        if not order:
            return {'success': False, 'error': 'Invalid order reaquest.'}

        recipient_name = order['billing'].get('first_name', '') + ' ' + order['billing'].get('last_name', '')
        recipient_phone = order['billing'].get('phone', '')
        recipient_address = order['billing'].get('address_1', '')

        merchant_invoice_id = str(order.get('id', ''))
        cash_collection_amount = float(order.get('total', 0))
        
        order_id = order.get('order_id')

        url = f"{self.base_url}/create_order"
        headers = {
            'api-Key': self.api_key,
            'secret-Key': self.secret_key,
            'Content-Type': 'application/json',
        }
        payload = {
            'invoice': datetime.now().strftime('%y%m%d') + '-' + str(order.get('id')),
            'recipient_name': recipient_name,
            'recipient_phone': recipient_phone,
            'recipient_address': recipient_address,
            'cod_amount': cash_collection_amount,
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 401:
                return {'success': False, 'error': f'Invalid api key and secret. Try again.'}
            
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status') == 200:
                consignment = response_data.get('consignment')
                return {
                    'success': True,
                    'order_id':order_id,
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
                'order_id':order_id,
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
        elif status.lower() == 'return' or 'return' in status.lower():
            return 'Refunded'
        else:
            return 'Processing'
