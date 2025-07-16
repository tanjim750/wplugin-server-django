from django.http import JsonResponse, HttpResponse
from .models import *
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.utils.timezone import make_aware as make_django_timezone_aware
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
# import spacy
# from spacy.matcher import PhraseMatcher
from urllib.parse import urlparse


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
        license_key:str = data.get('license_key','')
        domain = data.get('domain')
    except Exception:
        return JsonResponse({'success':False,'error': 'Invalid data'}, status=400)

    try:
        # print(license_key,domain)
        license = License.objects.get(key=license_key.strip(),domain=domain)
        # print("license",license)

        is_valid = license.is_valid()
        expire_date = license.expires_at.date() if license.expires_at else "lifetime"

        if expire_date == "lifetime":
            expire_label = "You have lifetime subscription plan."
        else:
            expire_label = f"You have access until {str(expire_date)}"

        return JsonResponse({
            'success':True,
            'valid': is_valid,
            'expire_date':expire_date,
            'expire_label':expire_label
        },status=200)

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
            orders = data.get('data', None)
            platform = data.get('platform',None)
            test_mode = data.get('test_mode',False)

            # print(license_key,domain,credentials,platform)

            if not (license_key and domain and credentials and orders and platform):
                return JsonResponse({
                    'success':False,
                    'error':'Please provide valid data'
                },status=400) 

            license = License.objects.filter(key=license_key,domain=domain)

            if not license.exists() and not license.first().is_valid():
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
            if type(orders) != list:
                orders = [orders]
                
            results = []
            for order in orders:
                response = courier.create_parcel(order)
                response['order_id'] = order.get('order_id')
                results.append(response)

            print(results)

            if not results:
                status=400
            else:
                status=200
            
            return JsonResponse({
                'success': True,
                'results': results
            },status=status)

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

            if not license.exists() and not license.first().is_valid():
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
        phone = request.POST.get('phone',None)
        email = request.POST.get('email',None)
        expires_at = request.POST.get('expiry',None)
        domain = request.POST.get('domain',None)

        if not customer_name or not expires_at or not domain:
            return JsonResponse({
                'success':False,
                'message':'Invalid request.'
            })
        
        try:
            license_key = self.generate_license_key()
            expiry_datetime = make_django_timezone_aware(datetime.strptime(expires_at, "%Y-%m-%d"))

            while License.objects.filter(key=license_key).exists():
                license_key = self.generate_license_key()

            license = License.objects.create(
                customer_name = customer_name,
                phone=phone,
                email = email,
                key= license_key,
                domain = domain,
                expires_at = expiry_datetime
            )

            license.save()

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

            if not license.exists() and not license.first().is_valid():
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

            # print(data)

            license_key = data.get('license_key',None)
            domain = data.get('domain', None)
            pixel_id = data.get('pixel_id',None)
            access_token = data.get('access_token',None)
            test_event = data.get('test_event',None)
            event_id = data.get('event_id',None)
            event = data.get('event',None)
            payload = data.get('details',None)

            if not (license_key and domain and pixel_id and access_token and event):
                return JsonResponse({
                    'success':False,
                    'error':'Missing required data.'
                },status=400)

            license = License.objects.filter(key=license_key,domain=domain)
            fb_event = FacebookEvent.objects.filter(text__iexact=event)

            if not license.exists() and not license.first().is_valid():
                return JsonResponse({
                    'success':False,
                    'error':'Invalid plugin licence key.'
                },status=400)

            if not fb_event.exists():
                return JsonResponse({
                    'success':False,
                    'error':'No standard event found.'
                },status=400)

            
            manager = EventManager(
                pixel_id=pixel_id,
                access_token=access_token,
                test_code=test_event,
                event_id = event_id
            )
            
            fb_event_name = fb_event.first().event_name
            result = manager.send_event(fb_event_name,payload)
            # print(result)
            # save event request data
            try:
                thread1 = threading.Thread(target=self.save_event_request, args=(license.first(),event,
                            fb_event_name,fb_event.first(),data,result))
                thread1.start()
            except:
                pass

            return JsonResponse(result, status=200 if result['success'] else 200)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON payload'}, status=400)
        except Exception as e:
            # print(e)
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        
    def save_event_request(self,customer,event_request,standard_event,event_ins,event_data,response):
        is_success = response.get('success',False)
        fbtrace_id = response.get('response',{}).get('fbtrace_id',None)

        return FacebookEventRequest.objects.create(
            event= event_ins,
            customer = customer,
            event_request = event_request,
            standard_event = standard_event,
            fbtrace_id = fbtrace_id,
            is_success = is_success,
            request_data = event_data
        )

class GetAllFacebookEvents(View):
    def get(self,request):
        events = list(FacebookEvent.objects.all().values())
        return JsonResponse({'events': events}, status=200)


class UserMessageExtractor:
    SERVICE_KEYWORDS = [
        "digital marketing", "marketing consultancy", "website development",
        "tracking", "analytics", "facebook ads", "tiktok marketing",
        "product design", "ui design", "ux design", "automation",
        "chatbot", "app development"
    ]

    def __init__(self, message_text):
        self.text = message_text
        self.lower_text = message_text.lower()
        self.nlp = spacy.load("en_core_web_sm")
        self.doc = self.nlp(message_text)

    def extract_email(self):
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', self.lower_text)
        return match.group(0) if match else None

    def extract_phone(self):
        match = re.search(r'(\+?\d[\d\s\-\(\)]{7,20})', self.lower_text)
        return match.group(0) if match else None

    def extract_budget(self):
        for ent in self.doc.ents:
            if ent.label_ == "MONEY":
                return ent.text
        match = re.search(r'(?:(?:৳|\$|tk)?\s?\d{3,7}[kK]?)|(\d{3,7}\s?(tk|৳|\$))', self.lower_text)
        return match.group(0) if match else None

    def extract_facebook_url(self):
        match = re.search(r'(https?:\/\/)?(www\.)?facebook\.com\/[A-Za-z0-9\.\-_]+', self.lower_text)
        return match.group(0) if match else None

    def extract_generic_url(self):
        for token in self.doc:
            if token.like_url:
                # Exclude Facebook URLs if they are handled separately
                if "facebook.com" not in token.text:
                    return token.text
        return None

    def extract_name(self):
        for ent in self.doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
        match = re.search(r"(?:my name is|i am|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", self.text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def extract_location(self):
        for ent in self.doc.ents:
            if ent.label_ in ["GPE", "LOC"]:
                return ent.text
        match = re.search(r"(from|based in|located at)\s+([A-Za-z\s]+)", self.lower_text, re.IGNORECASE)
        return match.group(2).strip() if match else None

    def extract_services(self):
        matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        patterns = [self.nlp.make_doc(service) for service in self.SERVICE_KEYWORDS]
        matcher.add("SERVICES", patterns)

        matches = matcher(self.doc)
        found_services = list(set(self.doc[start:end].text for _, start, end in matches))
        return found_services

    def extract_business(self):
        # Primary: spaCy NER for ORG
        for ent in self.doc.ents:
            if ent.label_ == "ORG":
                return ent.text.strip()
            
    def extract_all(self):
        return {
            "email": self.extract_email(),
            "phone": self.extract_phone(),
            "budget": self.extract_budget(),
            "facebook_url": self.extract_facebook_url(),
            "website": self.extract_generic_url(),
            "name": self.extract_name(),
            "location": self.extract_location(),
            "services": self.extract_services(),
            'business': self.extract_budget()
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

                        # print(sender_id)

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
                            if not more_than_2_minutes and first_user.auto_message:
                                is_send_bot_msg = True
                            elif user_last_updated_hours_difference > 6:
                                is_send_bot_msg = True
                                first_user.auto_message = True
                                first_user.updated_at = timezone.now()
                                first_user.save()

                            if first_user.is_blocked:
                                is_send_bot_msg = False

                        

                        if is_send_bot_msg:
                            try:
                                response_text = self.gemini_rag.generate_answer_native(sender_id,message_text)
                            except Exception as e:
                                # traceback.print_exc()
                                response_text = "Thank you. Our Supoort agent will contact with you Soon."
                            # print(f"Received message from {sender_id}: {response_text}")

                            claimed_trial = self.claim_zyncops_trail(response_text,sender_id)
                            sent_response_status_codes = []

                            if claimed_trial:
                                sent_response = self.send_message(sender_id,claimed_trial)
                                sent_response_status_codes.append(sent_response.status_code)
                            else:
                                response_chunks = self.split_llm_response_by_chunks(response_text)
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
                                user= user.first(),
                                text = message_text,
                                response = "no response. assume a respnse.",
                                mid = ""
                            )
                            
                    elif 'delivery' in messaging_event:
                        mids = messaging_event['delivery'].get('mids',[])
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
        # extractor = UserMessageExtractor(message)
        # data = extractor.extract_all()

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

        # if data['email']:
        #     UserEmail.objects.create(
        #         user = user,
        #         message = user_message,
        #         email = data['email']
        #     )
        # if data['phone']:
        #     UserPhone.objects.create(
        #         user = user,
        #         message = user_message,
        #         phone = data['phone']
        #     )
        # if data['location']:
        #     UserAddress.objects.create(
        #         user = user,
        #         message = user_message,
        #         address = data['location']
        #     )
        # if data['budget']:
        #     UserBudget.objects.create(
        #         user = user,
        #         message = user_message,
        #         amount = data['budget']
        #     )
        # if data['facebook_url']:
        #     UserFacebookURL.objects.create(
        #         user = user,
        #         message = user_message,
        #         url = data['facebook_url']
        #     )
        # if data['website']:
        #     UserWebsite.objects.create(
        #         user= user,
        #         message = user_message,
        #         url = data['website']
        #     )
        # if data['services']:
        #     UserService.objects.create(
        #         user= user,
        #         message = user_message,
        #         service = data['services']
        #     )

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
        
    def claim_zyncops_trail(self,text:str,user_id):
        if 'create_token' not in text.strip():
            return None
        
        user = MessengerUser.objects.filter(psid=user_id)
        
        if user.exists() and user.first().trial_claimed:
            return "দুঃখিত আপনি ইতিমধ্যেই আমাদের ট্রায়াল ভার্সন টি ব্যবহার করে ফেলেছেন। আপনি আমাদের মাসিক এবং বাৎসরিক সাবস্ক্রিপশনটি কেনার জন্য প্রযোজ্য। ধন্যবাদ"

        if user.exists():
            user = user.first()
        
        extract_data = self.parse_llm_response(text)

        name = extract_data['name']
        domain = self.extract_domain(extract_data['website']) if extract_data['website'] else None
        three_days_datetime = timezone.now() + timedelta(days=3)

        if name and user.name is None:
            
            user.name = name
            user.save()

        missing_fields = []
        if not name:
            missing_fields.append("name")
        if not domain:
            missing_fields.append("domain")

        if missing_fields:
            return f"অনুগ্রহ করে আপনার { ' এবং '.join(missing_fields) } প্রদান করুন।"
        
        if License.objects.filter(domain=domain).exists():
            user.first().trial_claimed = True
            user.first().save()
            return "দুঃখিত আপনি ইতিমধ্যেই আমাদের ট্রায়াল ভার্সন টি ব্যবহার করে ফেলেছেন। আপনি আমাদের মাসিক এবং বাৎসরিক সাবস্ক্রিপশনটি কেনার জন্য প্রযোজ্য। ধন্যবাদ"
        
        license_key = self.generate_license_key()
        while License.objects.filter(key=license_key).exists():
            license_key = self.generate_license_key()

        zyncops_file = ZyncopsPlugin.objects.last()

        download_url = "https://zyncops.triizync.com"
        if zyncops_file:
            download_url += zyncops_file.file.url

        new_license = License.objects.create(
            customer_name = name,
            key= license_key,
            domain = domain,
            expires_at = three_days_datetime
        )
        
        user.trial_claimed = True
        user.save()

        return f"আপনার লাইসেন্স কি সফলভাবে তৈরি করা হয়ে গেছে। আপনাকে লাইসেন্স কি এবং plugin  ডাউনলোড লিংক দেওয়া হচ্ছে:\n\n key: {license_key}\ndownload: {download_url}"


    def parse_llm_response(self,response: str) -> dict:
        # Define regex patterns for each field
        name_pattern = r'name:\s*(.+)'
        website_pattern = r'website:\s*(https?://[^\s]+)'
        number_pattern = r'number:\s*(\+?\d{6,15})'
        business_pattern = r'business:\s*(.+)'

        # Extract values using regex
        name = re.search(name_pattern, response, re.IGNORECASE)
        website = re.search(website_pattern, response, re.IGNORECASE)
        number = re.search(number_pattern, response, re.IGNORECASE)
        business = re.search(business_pattern, response, re.IGNORECASE)

        return {
            'name': name.group(1).strip() if name else None,
            'website': website.group(1).strip() if website else None,
            'number': number.group(1).strip() if number else None,
            'business': business.group(1).strip() if business else None,
        }

    
    def generate_license_key(self,length=30, segment_length=10):
        characters = string.ascii_uppercase + string.digits
        key = ''.join(random.choices(characters, k=length))
        segments = [key[i:i+segment_length] for i in range(0, length, segment_length)]
        return ''.join(segments)
    
    def extract_domain(self, url):
        """
        Extracts the domain name from a URL.
        Example: 'https://www.example.com/path' -> 'example.com'
        """
        if not url:
            return None
        try:
            # Add a scheme if missing, as urlparse works best with it
            if '://' not in url:
                url = 'http://' + url
            
            # Parse the URL and get the network location part
            netloc = urlparse(url).netloc
            
            # Remove 'www.' prefix if it exists
            if netloc.startswith('www.'):
                netloc = netloc[4:]
                
            return netloc
        except Exception:
            # Return None if any parsing error occurs
            return None