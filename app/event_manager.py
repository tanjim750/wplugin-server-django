import hashlib
import time
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.serverside.event import Event
from facebook_business.adobjects.serverside.content import Content
from facebook_business.adobjects.serverside.user_data import UserData
from facebook_business.adobjects.serverside.custom_data import CustomData
from facebook_business.adobjects.serverside.event_request import EventRequest
from facebook_business.adobjects.serverside.action_source import ActionSource
from facebook_business.adobjects.serverside.delivery_category import DeliveryCategory


import traceback,random

class EventManager:
    def __init__(self, pixel_id, access_token, test_code=None):
        self.pixel_id = pixel_id
        self.access_token = access_token
        self.test_code = test_code

        FacebookAdsApi.init(access_token=self.access_token)

    def hash_data(self, value):
        if value:
            return hashlib.sha256(value.strip().lower().encode()).hexdigest()
        return None
    
    def generate_fbp(self):
        timestamp = int(time.time())
        random_part = random.randint(1000000000000000, 9999999999999999)
        return f"fb.1.{timestamp}.{random_part}"
    
    def generate_fbc(self):
        timestamp = int(time.time())
        click_id = random.randint(1000000000000000, 9999999999999999)
        return f"fb.1.{timestamp}.{click_id}"

    def build_user_data(self, customer):
        return UserData(
            email=self.hash_data(customer.get("email")),
            phone=self.hash_data(customer.get("phone")),
            first_name=self.hash_data(customer.get("first_name")),
            last_name=self.hash_data(customer.get("last_name")),
            city=self.hash_data(customer.get("city")),
            state=self.hash_data(customer.get("state")),
            client_ip_address=customer.get("ip_address"),
            client_user_agent=customer.get("user_agent"),
            fbc = customer.get("fbc"),
            fbp = customer.get("fbp"),
            external_id=self.hash_data(customer.get("email"))  # optional but improves matching
        )
    
    def build_contents(self, payload):
        contents_list = []
        contents=payload.get("contents")

        for con in contents:
            contents_list.append(
                Content(
                    product_id=con.get('id'),
                    title=con.get('name',''),
                    item_price=con.get('price',0),
                    quantity=con.get('quantity',1),
                    delivery_category=DeliveryCategory.HOME_DELIVERY,
                )
            )

        return contents_list

    def build_custom_data(self, payload):
        currency=payload.get("currency",None)
        value=payload.get("value",None)
        order_id=payload.get("id",None)
        content_type = payload.get("content_type",None)

        if not (currency and value):
            return None
        
        return CustomData(
            currency=currency,
            value=float(value) if value else 0,
            order_id=order_id,
            contents=self.build_contents(payload),
            content_type=content_type
        )

    def send_event(self,event_name, payload):
        try:
            user_data = self.build_user_data(payload.get("customer", {}))
            # print(user_data)
            custom_data = self.build_custom_data(payload)

            event = Event(
                event_name=event_name,
                event_time=payload.get("event_time", int(time.time())),
                user_data=user_data,
                custom_data=custom_data,
                action_source=ActionSource.WEBSITE,
                event_source_url= payload.get('source_url',None)
            )
            
            request = EventRequest(
                events=[event],
                pixel_id=self.pixel_id,
                access_token=self.access_token,
                test_event_code=self.test_code  # optional for test events
            )

            response = request.execute()
            return {"success": True, "response": response.to_dict()}
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": str(e)}
