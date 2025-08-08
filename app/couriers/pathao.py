import requests
import logging,time
from datetime import datetime, timedelta


login_user = {
    "token": "",
    "expires_in": 0,
    "refresh_token": "",
    "token_acquired_at": 0
}

class PathaoAPI:
    def __init__(self, client_id, client_secret, username, password,test_mode=True):
        self.base_url = 'https://courier-api-sandbox.pathao.com' if test_mode else 'https://api-hermes.pathao.com'

        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password

        self.access_token = None
        self.token_expiry_at = None

        self.issue_token()
        # print('....init')

    def login(self):
        """Login to Pathao API and store token, expiry, and refresh token."""
        try:
            url = f"{self.base_url}/aladdin/api/v1/external/login"
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            session = requests.Session()
            resp = session.post(url, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json()

                token = data.get("access_token")
                if token:
                    login_user["token"] = token
                    login_user["expires_in"] = data.get("expires_in", 0)
                    login_user["refresh_token"] = data.get("refresh_token", "")
                    login_user["token_acquired_at"] = time.time()

                    print("[SUCCESS] Pathao login successful.")
                    return True
                else:
                    print("[ERROR] Pathao No token in response.")
                    return False
            else:
                print(f"[ERROR] Pathao Login failed. Status: {resp.status_code}, Response: {resp.text}")
                return False

        except Exception as e:
            print(f"[ERROR] Pathao Exception during Pathao login: {e}")
            return False
        
    def courier_ratio(self, phone):
        """Fetch Pathao courier success ratio for a given phone number."""
        try:
            # Ensure we have a valid token, otherwise login
            if not login_user["token"] or (time.time() - login_user["token_acquired_at"] > login_user["expires_in"]):
                print("[INFO] Pathao Token missing or expired, logging in again...")
                if not self.login():
                    return {
                "total_parcel": 0,
                "success_parcel": 0,
                "cancelled_parcel": 0,
                "success_ratio": 0
            }

            url = "https://merchant.pathao.com/api/v1/user/success"
            payload = {"phone": phone}
            headers = {
                "Authorization": f"Bearer {login_user['token']}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            resp = requests.post(url, json=payload, headers=headers)

            if resp.status_code == 200:
                data = resp.json().get("data", {})

                # Convert to requested format
                result = {
                    "total_parcel": data.get("customer", {}).get("total_delivery", 0),
                    "success_parcel": data.get("customer", {}).get("successful_delivery", 0),
                    "cancelled_parcel": data.get("customer", {}).get("total_delivery", 0) - data.get("customer", {}).get("successful_delivery", 0),
                    "success_ratio": data.get("success_rate", 0)
                }
                return result
            else:
                print(f"[ERROR] Pathao Failed to get courier ratio. Status: {resp.status_code}, Response: {resp.text}")
                return {
                "total_parcel": 0,
                "success_parcel": 0,
                "cancelled_parcel": 0,
                "success_ratio": 0
            }

        except Exception as e:
            print(f"[ERROR] Pathao Exception in courier_ratio: {e}")
            return {
                "total_parcel": 0,
                "success_parcel": 0,
                "cancelled_parcel": 0,
                "success_ratio": 0
            }


    def issue_token(self):
        url = f"{self.base_url}/aladdin/api/v1/issue-token"
        payload = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'password',
            'username': self.username,
            'password': self.password,
        }
        print(payload)
        try:
            response = requests.post(url, json=payload, timeout=20)
            # print(response.status_code)
            # response.raise_for_status()
            data = response.json()
            if 'access_token' in data and 'expires_in' in data:
                access_token = data['access_token']
                expires = data.get('expires_in')

                now = datetime.now()
                expiry_at = now + timedelta(seconds=int(expires))
                
                print(access_token,expiry_at)
                self.access_token = access_token
                self.token_expiry_at = expiry_at
            
        except Exception as e:
            # print(e)
            pass

    def get_first_store(self):
        now = datetime.now()
        if now > self.token_expiry_at:
            self.issue_token()

        url = f"{self.base_url}/aladdin/api/v1/stores"
        headers = {
            'Content-Type': 'application/json; charset=UTF-8',
            'Authorization': f'Bearer {self.access_token}',
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            stores = data.get('data', {}).get('data', [])
            if not stores:
                # logging.error('No store found in Pathao response.')
                return None

            store = stores[0]
            return {
                'store_id': store['store_id'],
                'city_id': store['city_id'],
                'zone_id': store['zone_id'],
            }

        except requests.RequestException as e:
            # logging.error(f'Pathao store fetch failed: {str(e)}')
            return None

    def create_parcel(self, order):
        # print("create................")
        if not self.access_token:
            return {'success':False, 'error': 'Invalid credentials. Try again.'}
        # now = datetime.now()
        # if now > self.token_expiry_at:
        #     self.issue_token()

    
        store = self.get_first_store()
        if not store:
            return {'success':False, 'error': 'No Pathao store found. Please create a store in Pathao.'}

        url = f"{self.base_url}/aladdin/api/v1/orders"

        recipient_name = order['billing'].get('first_name', '') + ' ' + order['billing'].get('last_name', '')
        recipient_phone = order['billing'].get('phone', '')
        recipient_address = order['billing'].get('address_1', '')

        # Optional fallback logic to derive delivery area and ID (e.g., from state)
        delivery_area = order['billing'].get('state', '')  # You can replace this with logic to convert state to area name
        delivery_area_id = 1  # Example static mapping for 'BD-13' or look up dynamically

        merchant_invoice_id = str(order.get('id', ''))
        cash_collection_amount = float(order.get('total', 0))
        parcel_weight = 1.0  # Assign default or calculate from product data
        value = float(order.get('total', 0))

        payload = {
            'store_id': int(store['store_id']),
            'recipient_name': recipient_name,
            'recipient_phone': recipient_phone,
            'recipient_address': recipient_address,
            'recipient_city': int(store['city_id']),
            'recipient_zone': int(store['zone_id']),
            'delivery_type': 48,
            'item_type': 2,
            'item_quantity': sum(item.get('quantity', 1) for item in order.get('items', [])),
            'item_weight': 0.5,
            'amount_to_collect': cash_collection_amount
        }

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.access_token}',
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            body = response.json()
            print(body)
            if 'errors' in body:
                error_details = body['errors']
                error_message = ' '.join(
                    f"{key}: {', '.join(val)}" for key, val in error_details.items()
                )

                return {
                    'success':False,
                    'error':error_message
                }
            
            if body.get('code') == 200:
                data = body.get('data')
                return {
                    'success': True,
                    'message': body.get('message', 'Success'),
                    'tracking_id': data.get('consignment_id')
                }
            
            response.raise_for_status()

        except Exception as e:
            # logging.error(f'Failed to create Pathao parcel: {str(e)}')
            return {'success':False, 'error': f'Failed to create Pathao parcel.'}
        
    
    def get_parcel_status(self, consignment_id):
        url = f"{self.base_url}/aladdin/api/v1/orders/{consignment_id}/info"
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        try:
            response = requests.get(url, headers=headers)
            # response.raise_for_status()
            result = response.json()

            # return result

            if result.get("type") == "success":
                return {
                    'success':True,
                    "status": result["data"]["order_status"],
                    "updated_at": result["data"]["updated_at"],
                }
            else:
                # print(f"API error: {result.get('message')}")
                return {
                    'success':False,
                    'error':result.get('message','Invalid tracking id. Try again')
                }

        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return None
        
    def track_parcel(self, tracking_code):
        url = "https://merchant.pathao.com/api/v1/user/tracking"

        payload = {
            'consignment_id': tracking_code,
        }

        headers = {
            'Content-Type': 'application/json',
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()

            if 'data' in body:
                data = body['data']

                return {
                    'success':True,
                    'status': self.convert_to_wp_status(data['order'].get('transfer_status','')),
                    'tracking': data['log'],
                }
            
            return {
                    'success':False,
                    'error': 'No tracking info found.'
                }

        except Exception as e:
            # logging.error(f'Failed to create Pathao parcel: {str(e)}')
            return {
                    'success':False,
                    'error': 'No tracking info found.'
                }
        
    def convert_to_wp_status(self,status:str):
        if status.lower() == 'delivered' or 'delivered' in status.lower():
            return 'Completed'
        elif status.lower() == 'cancelled' or 'cancelled' in status.lower():
            return 'Cancelled'
        elif status.lower() == 'return' or 'return' in status.lower():
            return 'Refunded'
        else:
            return 'Processing'
        
    

