from django.http import JsonResponse, HttpResponse
from .models import *
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.views import View
from django.forms.models import model_to_dict
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


import json
import random
import string
import requests
from datetime import datetime, timedelta
import traceback
import threading
import re


from app.couriers.redx import RedxAPI
from app.couriers.steadfast import SteadFastAPI
from app.couriers.pathao import PathaoAPI

from app.event_manager import EventManager
from app.gemini_rag import Gemini_RAG

@csrf_exempt
def verify_license(request):
    if request.method != 'POST':
        return JsonResponse({'success':False,'error': 'Invalid method'}, status=405)

    try:
        data = json.loads(request.body)
        license_key = data.get('license_key')
        domain = data.get('domain')
    except Exception:
        return JsonResponse({'success':False,'error': 'Invalid data'}, status=400)

    try:
        license = License.objects.get(key=license_key,domain=domain)
        is_valid = license.is_valid()
        return JsonResponse({'success':True,'valid': is_valid},status=200)
    except License.DoesNotExist:
        return JsonResponse({'success':False,'valid': False},status=400)
    
    
@method_decorator(csrf_exempt, name='dispatch')
class CreateParcel(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def post(self,request):
        try:
            data = json.loads(request.body)
            license_key = data.get('license_key',None)
            domain = data.get('domain', None)
            credentials = data.get('credentials', None)
            order = data.get('data', None)
            platform = data.get('platform',None)
            test_mode = data.get('test_mode',False)

            # print(license_key,domain,credentials,platform)

            if not (license_key and domain and credentials and order and platform):
                return JsonResponse({
                    'success':False,
                    'error':'Please provide valid data'
                },status=400)

            license = License.objects.filter(key=license_key,domain=domain)

            if not license.exists():
                return JsonResponse({
                    'success':False,
                    'error':'Invalid plugin licence key.'
                },status=400)
            
            courier = None
            if platform.lower() == 'redx':
                courier = RedxAPI(credentials.get('api_key',''),test_mode)
            if platform.lower() == 'steadfast':
                courier = SteadFastAPI(credentials.get('api_key',''),'iygpijrmddyuxbfgueqfwbrz')
            if platform.lower() == 'pathao':
                courier = PathaoAPI(
                    credentials.get('client_id',''),
                    credentials.get('client_secret',''),
                    credentials.get('username',''),
                    credentials.get('password',''),
                    test_mode
                )

            if not courier:
                return JsonResponse({
                    'success':False,
                    'error':'Invalid platform. Valid platforms are Redx, SteadFast and Pathao'
                }, status=400)
            
            # print(credentials['api_key'])
            
            response = courier.create_parcel(order)

            if 'error' in response:
                status=400
            else:
                status=200
            
            return JsonResponse(response,status=status)

        except Exception as e:
            print(e)
            return JsonResponse({'success':False,'error': f"Please provide valid data",}, status=400)
        

        

@method_decorator(csrf_exempt, name='dispatch')
class TrackParcel(View):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def post(self,request):
        try:
            data = json.loads(request.body)
            license_key = data.get('license_key',None)
            domain = data.get('domain', None)
            tracking_id = data.get('tracking_id',None)
            credentials = data.get('credentials', None)
            platform = data.get('platform',None)
            test_mode = data.get('test_mode',False)

            # print(license_key,domain,credentials,platform)

            if not (license_key and domain and credentials and platform and tracking_id):
                return JsonResponse({
                    'success':False,
                    'error':'Please provide valid data'
                },status=400)

            license = License.objects.filter(key=license_key,domain=domain)

            if not license.exists():
                return JsonResponse({
                    'success':False,
                    'error':'Invalid plugin licence key.'
                },status=400)
            
            courier = None
            if platform.lower() == 'redx':
                courier = RedxAPI(credentials.get('api_key',''),test_mode)
            if platform.lower() == 'steadfast':
                courier = SteadFastAPI(credentials.get('api_key',''),credentials.get('secret_key',''))
            if platform.lower() == 'pathao':
                courier = PathaoAPI(
                    credentials.get('client_id',''),
                    credentials.get('client_secret',''),
                    credentials.get('username',''),
                    credentials.get('password',''),
                    test_mode
                )

            if not courier:
                return JsonResponse({
                    'success':False,
                    'error':'Invalid platform. Valid platforms are Redx, SteadFast and Pathao'
                }, status=400)
            
            # print(credentials['api_key'])
            
            response = courier.track_parcel(tracking_id)

            if 'error' in response:
                status=400
            else:
                status=200
            
            # print(response)
            return JsonResponse(response,status=status)

        except Exception as e:
            # print(e)
            return JsonResponse({'success':False,'error': f"Please provide valid data."}, status=400)



class GenerateKey(View):
    def get(self,request):
        if not request.user.is_authenticated:
            return HttpResponse('Page not found!!')
        return render(request,'generate_key.html')
    
    def post(self,request):
        customer_name = request.POST.get('name',None)
        expires_at = request.POST.get('expiry',None)
        domain = request.POST.get('domain',None)

        if not customer_name or not expires_at or not domain:
            return JsonResponse({
                'success':False,
                'message':'Invalid request.'
            })
        
        try:
            license_key = self.generate_license_key()
            expiry_datetime = datetime.strptime(expires_at, "%Y-%m-%d")

            while License.objects.filter(key=license_key).exists():
                license_key = self.generate_license_key()

            license = License.objects.create(
                customer_name = customer_name,
                key= license_key,
                domain = domain,
                expires_at = expiry_datetime
            )

            return JsonResponse(model_to_dict(license))
        
        except Exception as e:
            return JsonResponse({
                'success':False,
                'error': str(e)
            })
    

    def generate_license_key(self,length=30, segment_length=10):
        characters = string.ascii_uppercase + string.digits
        key = ''.join(random.choices(characters, k=length))
        segments = [key[i:i+segment_length] for i in range(0, length, segment_length)]
        return ''.join(segments)
    

@method_decorator(csrf_exempt, name='dispatch')
class FraudCheck(View):
    def post(self,request):
        try:
            data = json.loads(request.body)
            license_key = data.get('license_key',None)
            domain = data.get('domain', None)
            phone = data.get('phone',None)
            order = data.get('order',{})
            # print(order)

            if order:
                name = order['billing'].get('first_name', '') + ' ' + order['billing'].get('last_name', '')
                address = order['billing'].get('address_1', '')
                items = order.get('items', [])

                # print(name)
                if phone and address and name:
                    thread1 = threading.Thread(target=self.save_customer, args=(name,phone,address,items))
                    thread1.start()

            # print(license_key,domain,phone)

            if not (license_key and domain and phone):
                return JsonResponse({
                    'success':False,
                    'error':'Please provide valid data'
                },status=400)

            license = License.objects.filter(key=license_key,domain=domain)

            if not license.exists():
                return JsonResponse({
                    'success':False,
                    'error':'Invalid plugin licence key.'
                },status=400)
            
            response = self.fetch_courier_stats(phone)
            # print(response)
            return JsonResponse(response)
        
        except Exception as e:
            print(e)
            return JsonResponse({'success':False,'error': f"Sorry, Something went worng."}, status=400)
        
    
    def save_customer(self,name,phone,address,items):
        customer = Customer.objects.filter(phone=phone)

        if customer.exists():
            return
        
        Customer.objects.create(
            name=name,
            phone=phone,
            address=address,
            items = items
        )

        return
        
    def fetch_courier_stats(self,phone_number):
        formatted_phone:str = phone_number.strip()
        bd_phone = formatted_phone.replace('+88','',1) if formatted_phone.startswith('+88') else formatted_phone

        stats = {}

        try:
            pathao_url = "https://bdcourier.com/api/courier-check"
            body = {"phone": formatted_phone}
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f"Bearer IfXG4thl1zauNDck1wJqpuMlaJ5qh58t4ev8HnqGTgmFA9HlDDY7biqs44nx",
            }

            res = requests.post(pathao_url, json=body, headers=headers)

            data = res.json().get("courierData", {})
            # print(data)
            pathao = data.get('pathao')
            redx = data.get('redx')
            steadfast = data.get('steadfast')
            paperfly = data.get('paperfly')

            stats['redx'] = {
                'total': redx.get('total_parcel',0),
                'success': redx.get('success_parcel',0),
                'cancel': redx.get('cancelled_parcel',0),
                'cancelRatio': (redx.get('cancelled_parcel',0) / redx.get('total_parcel',0) * 100) if redx.get('total_parcel',0) > 0 else 0,
            }

            stats['pathao'] = {
                'total': pathao.get('total_parcel',0),
                'success': pathao.get('success_parcel',0),
                'cancel': pathao.get('cancelled_parcel',0),
                'cancelRatio': (pathao.get('cancelled_parcel',0) / pathao.get('total_parcel',0) * 100) if pathao.get('total_parcel',0) > 0 else 0,
            }

            stats['steadfast'] = {
                'total': steadfast.get('total_parcel',0),
                'success': steadfast.get('success_parcel',0),
                'cancel': steadfast.get('cancelled_parcel',0),
                'cancelRatio': (steadfast.get('cancelled_parcel',0) / steadfast.get('total_parcel',0) * 100) if steadfast.get('total_parcel',0) > 0 else 0,
            }

            stats['paperfly'] = {
                'total': paperfly.get('total_parcel',0),
                'success': paperfly.get('success_parcel',0),
                'cancel': paperfly.get('cancelled_parcel',0),
                'cancelRatio': (paperfly.get('cancelled_parcel',0) / paperfly.get('total_parcel',0) * 100) if paperfly.get('total_parcel',0) > 0 else 0,
            }

        
        except Exception as e:
            stats = {
                'redx': {'success': 0, 'cancel': 0, 'cancelRatio': 0}, 
                'steadfast': {'success': 0, 'cancel': 0, 'cancelRatio': 0}, 
                'pathao': {'success': 0, 'cancel': 0, 'cancelRatio': 0},
                'paperfly': {'success': 0, 'cancel': 0, 'cancelRatio': 0}
            }
            # print("Pathao error:", e)
            # traceback.print_exc()

        return stats
    

@method_decorator(csrf_exempt, name='dispatch')
class TriggerFbEventView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)

            print(data)

            license_key = data.get('license_key',None)
            domain = data.get('domain', None)
            pixel_id = data.get('pixel_id',None)
            access_token = data.get('access_token',None)
            test_event = data.get('test_event',None)
            current_status = data.get('current_status',None)
            old_status = data.get('old_status',None)
            payload = data.get('details',None)

            if not (license_key and domain and pixel_id and access_token):
                return JsonResponse({
                    'success':False,
                    'error':'Missing required data.'
                },status=400)

            license = License.objects.filter(key=license_key,domain=domain)
            fb_event = FacebookEvent.objects.filter(text__iexact=current_status)

            if not fb_event.exists():
                return JsonResponse({
                    'success':False,
                    'error':'No standard event found.'
                },status=400)

            if not license.exists():
                return JsonResponse({
                    'success':False,
                    'error':'Invalid plugin licence key.'
                },status=400)

            if(current_status == old_status):
                return JsonResponse({'success': False, 'error': 'Current and old order status cannot be same.'}, status=400)


            manager = EventManager(
                pixel_id=pixel_id,
                access_token=access_token,
                test_code=test_event  # Optional for test events
            )
            
            fb_event_name = fb_event.first().event_name
            result = manager.send_event(fb_event_name,payload)
            print(result)
            return JsonResponse(result, status=200 if result['success'] else 200)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)
        except Exception as e:
            print(e)
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

class UserMessageExtractor:
    # Optional: Define known service keywords for extraction
    SERVICE_KEYWORDS = TrizyncService.objects.all().values_list('name',flat=True)

    def __init__(self, message_text):
        self.text = message_text.lower()

    def extract_email(self):
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', self.text)
        return match.group(0) if match else None

    def extract_phone(self):
        match = re.search(r'(\+?\d[\d\s\-\(\)]{7,20})', self.text)
        return match.group(0) if match else None

    def extract_budget(self):
        # Match currency followed by numbers, or vice versa (e.g., 5k, $5000, ৳1000)
        match = re.search(r'(?:(?:৳|\$|tk)?\s?\d{3,7}[kK]?)|(\d{3,7}\s?(tk|৳|\$))', self.text)
        return match.group(0) if match else None

    def extract_facebook_url(self):
        match = re.search(r'(https?:\/\/)?(www\.)?facebook\.com\/[A-Za-z0-9\.\-_]+', self.text)
        return match.group(0) if match else None

    def extract_generic_url(self):
        match = re.search(r'(https?:\/\/)?(www\.)?[a-zA-Z0-9\-]+\.[a-z]{2,}(\/[\w\-]*)*', self.text)
        return match.group(0) if match else None

    def extract_name(self):
        match = re.search(r"(?:my name is|i am|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", self.text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def extract_location(self):
        match = re.search(r"(from|based in|located at)\s+([A-Za-z\s]+)", self.text, re.IGNORECASE)
        return match.group(2).strip() if match else None

    def extract_services(self):
        found_services = []
        for keyword in self.SERVICE_KEYWORDS:
            if keyword.lower() in self.text:
                found_services.append(keyword)
        return found_services

    def extract_all(self):
        return {
            "email": self.extract_email(),
            "phone": self.extract_phone(),
            "budget": self.extract_budget(),
            "facebook_url": self.extract_facebook_url(),
            "website": self.extract_generic_url(),
            "name": self.extract_name(),
            "location": self.extract_location(),
            "services": self.extract_services()
        }


@method_decorator(csrf_exempt, name='dispatch')
class FacebookGraphAPI(View):
    def __init__(self, **kwargs):
        self.gemini_rag = Gemini_RAG()
        # self.gemini_rag.load_vectordb()
        self.access_token = PageAccessToken.objects.all().last().token

    def get(self,request):
        mode = request.GET.get('hub.mode',None)
        token = request.GET.get('hub.verify_token',None)
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe'and token == 'trizync':
            return HttpResponse(challenge,status=200)
        # body = json.loads(request.body)
        # print(request.body)
        return JsonResponse({'success':True})
    
    def post(self, request):
        body_unicode = request.body.decode('utf-8')
        data = json.loads(body_unicode)

        # Log for debug
        # print("Incoming webhook payload:", json.dumps(data, indent=2))

        if 'object' in data and data['object'] == 'page':
            for entry in data['entry']:
                for messaging_event in entry['messaging']:
                    if 'message' in messaging_event:
                        sender_id = messaging_event['sender']['id']
                        recipient_id = messaging_event['recipient']['id']
                        timestamp = messaging_event['timestamp']
                        message_text = messaging_event['message'].get('text')

                        # Convert given timestamp to datetime object
                        given_datetime = datetime.fromtimestamp(timestamp / 1000)
                        current_datetime = datetime.now()

                        # Calculate the difference
                        time_difference = current_datetime - given_datetime

                        # Check if the difference is more than 3 minutes
                        more_than_2_minutes = time_difference > timedelta(minutes=2)

                        user = MessengerUser.objects.filter(psid=sender_id)
                        is_send_bot_msg = False
                        
                        if not user.exists() and not more_than_2_minutes:
                            is_send_bot_msg = True
                        else:
                            first_user = user.first()
                            user_last_updated_difference =  user.first().updated_at - timezone.now()
                            user_last_updated_hours_difference = user_last_updated_difference.total_seconds() / 3600
                            if not more_than_2_minutes and user.first().auto_message:
                                is_send_bot_msg = True
                            elif user_last_updated_hours_difference > 6:
                                is_send_bot_msg = True
                                first_user.auto_message = True
                                first_user.updated_at = timezone.now()
                                first_user.save()

                        

                        if is_send_bot_msg:
                            try:
                                response_text = self.gemini_rag.generate_answer_native(sender_id,message_text)
                            except Exception as e:
                                # traceback.print_exc()
                                response_text = "Thank you. Our Supoort agent will contact with you Soon."
                            # print(f"Received message from {sender_id}: {message_text}")
                            response_chunks = self.split_llm_response_by_chunks(response_text)
                            sent_response_status_codes = []
                            for chunk in response_chunks:
                                sent_response = self.send_message(sender_id,chunk)
                                sent_response_status_codes.append(sent_response.status_code)

                            if 200 in sent_response_status_codes:
                                sent_response_json = sent_response.json()
                                sent_message_id = sent_response_json['message_id']
                                self.save_details(sender_id,message_text,response_text,sent_message_id)
                            # Now you can call a function to reply using Send API
                        if user.exists() and not user.first().auto_message:
                            UserMessage.objects.create(
                                user= user,
                                text = message_text,
                                response = "no response. assume a respnse.",
                                mid = ""
                            )
                    elif 'delivery' in messaging_event:
                        mids = messaging_event['delivery']['mids']
                        sender_id = messaging_event['sender']['id']
                        user = MessengerUser.objects.filter(psid=sender_id)

                        if user.exists():
                            user = user.first()
                        else:
                            user_details = self.get_user_profile(sender_id)
                            full_name = user_details.get('first_name','') +' '+ user_details.get('last_name','')
                            user = MessengerUser.objects.create(
                                psid = sender_id,
                                name = full_name,
                            )
                        
                        is_msg_exists = UserMessage.objects.filter(mid__in = mids)
                        if not is_msg_exists:
                            user.auto_message = False
                            user.updated_at = timezone.now()
                            
                        user.save()

        return JsonResponse({'status': 'ok'})
    
    def save_details(self,psid,message,response,sent_message_id,user_auto_message=True):
        user = MessengerUser.objects.filter(psid=psid)
        user_details = self.get_user_profile(psid)
        extractor = UserMessageExtractor(message)

        data = extractor.extract_all()

        full_name = user_details.get('first_name','') +' '+ user_details.get('last_name','')

        if not user.exists():
            user = MessengerUser.objects.create(
                psid = psid,
                name = full_name,
            )
        else:
            user = user.first()

        user.auto_message = user_auto_message
        user_message = UserMessage.objects.create(
            user= user,
            text = message,
            response = response,
            mid = sent_message_id
        )

        if data['email']:
            user.email = data['email']
        if data['phone']:
            user.phone = data['phone']
        if data['location']:
            user.location = data['location']
        if data['budget']:
            UserBudget.objects.create(
                user = user,
                message = user_message,
                amount = data['budget']
            )
        # if data['facebook_url']:
        #     user.facebook_url = data['facebook_url']
        if data['website']:
            UserWebsite.objects.create(
                user= user,
                message = user_message,
                url = data['website']
            )
        if data['services']:
            UserService.objects.create(
                user= user,
                message = user_message,
                service = data['services']
            )

        user.save()

    def send_message(self,recipient_id, message_text):
        url = "https://graph.facebook.com/v18.0/me/messages"
        headers = {
            "Content-Type": "application/json"
        }
        data = {
            "recipient": { "id": recipient_id },
            "message": { "text": message_text }
        }
        params = {
            "access_token": self.access_token
        }
        response = requests.post(url, headers=headers, params=params, json=data)
        # print("Send API response:", response.json())
        return response

    def get_user_profile(self,psid):
        url = f"https://graph.facebook.com/v18.0/{psid}"
        params = {
            'fields': 'first_name,last_name,profile_pic,locale',
            'access_token': self.access_token
        }
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return {}
    
    def split_llm_response_by_chunks(self,response_text):
        # Pattern matches (1/2), (2/3), etc.
        pattern = r'\(\d+\/\d+\)'
        if re.search(pattern, response_text):
            # Split by the chunk markers (assuming chunk start with (x/y))
            # This splits text at each occurrence of (number/number)
            parts = re.split(r'\(\d+\/\d+\)', response_text)
            # The first split part might be empty if text starts with (1/2), remove empties
            return [p.strip() for p in parts if p.strip()]
        else:
            # No chunk labels found, return full text as one part
            return [response_text.strip()]