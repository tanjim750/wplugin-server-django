from django.http import JsonResponse, HttpResponse
from .models import License
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.views import View
from django.forms.models import model_to_dict
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt


import json
import random
import string
import requests
from datetime import datetime
import traceback

from app.couriers.redx import RedxAPI
from app.couriers.steadfast import SteadFastAPI
from app.couriers.pathao import PathaoAPI

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
        return JsonResponse({'success':True,'valid': is_valid})
    except License.DoesNotExist:
        return JsonResponse({'success':True,'valid': False})
    
    
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

            print(license_key,domain,phone)

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
            return JsonResponse({'success':False,'error': f"Sorry, Something went worng."}, status=400)
        
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
            # print(res)

            data = res.json().get("courierData", {})
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