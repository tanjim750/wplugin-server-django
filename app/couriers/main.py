from redx import RedxAPI
from steadfast import SteadFastAPI
from pathao import PathaoAPI

import time


redx_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwiaWF0IjoxNzM1NTMxNjU2LCJpc3MiOiJ0OTlnbEVnZTBUTm5MYTNvalh6MG9VaGxtNEVoamNFMyIsInNob3BfaWQiOjEsInVzZXJfaWQiOjZ9.zpKfyHK6zPBVaTrYevnCqnUA-e2jFKQJ7lK-z4aOx2g"
redx_data = {
      "customer_name": "customer_name",
      "customer_phone": "01631596698",
      "delivery_area": "delivery_area",
      "delivery_area_id": 1,
      "customer_address": "customer_address",
      "merchant_invoice_id": "merchant_invoice_id",
      "cash_collection_amount": "222",
      "parcel_weight": "1",
      "value": "222",
      "is_closed_box": True,
  }

steadfast_data = {
            'invoice': "invoice-1313",
            'recipient_name': "recipient_name",
            'recipient_phone': "01631596698",
            'recipient_address': "recipient_address",
            'cod_amount': 624
        }

pathao_data = {
    'order_number': 'ORD1235',
    'total': 750,
    'billing': {'phone': '01631596698'},
    'shipping': {
        'first_name': 'John',
        'last_name': 'Doe',
        'phone': None,
        'address_1': 'Sector 1, Uttara',
        'city': 'Dhaka',
        'state': 'Dhaka'
    }
}

redx = RedxAPI(redx_key)
steadfast = SteadFastAPI('ayxqmqxx4cxlzajnlp2haxsu8xvq7q3a','iygpijrmddyuxbfgueqfwbrz')
pathao = PathaoAPI(
    base_url='https://courier-api-sandbox.pathao.com',
    client_id='7N1aMJQbWm',
    client_secret='wRcaibZkUdSNz2EI9ZyuXLlNrnAv0TdPUPXMnD39',
    username='test@pathao.com',
    password='lovePathao'
)

print(redx.track_parcel('20A316MOG0DI'))
print(steadfast.track_parcel('566E0AA4A'))
print(pathao.track_parcel('DB2311222W9K4L'))

# pathao_api = PathaoAPI(
#     base_url='https://sandbox.pathao.com',
#     client_id='7N1aMJQbWm',
#     client_secret='wRcaibZkUdSNz2EI9ZyuXLlNrnAv0TdPUPXMnD39',
#     username='test@pathao.com',
#     password='lovePathao'
# )

# Prepare order data
# order = {
#     'order_number': 'ORD123',
#     'total': 750,
#     'billing': {'phone': '01631596698'},
#     'shipping': {
#         'first_name': 'John',
#         'last_name': 'Doe',
#         'phone': None,
#         'address_1': 'Sector 1, Uttara',
#         'city': 'Dhaka',
#         'state': 'Dhaka'
#     }
# }



# time.sleep(5)

# api.get_first_store()
# result = api.track_parcel("DB2311222W9K4L")
# print(result)
