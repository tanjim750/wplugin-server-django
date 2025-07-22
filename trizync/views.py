from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from django.utils import timezone
from trizync.models import *

from decimal import Decimal
from django.db import transaction as db_transaction
from django.core.exceptions import ValidationError

from datetime import datetime
from calendar import monthrange
from collections import defaultdict
from django.db.models import Sum
import calendar

class ManageAccounts:
    @staticmethod
    def get_general_account():
        try:
            return Account.objects.get(is_general=True)
        except Account.DoesNotExist:
            raise ValidationError("No general account found.")

    def has_sufficient_expense_amount(amount):
        general = ManageAccounts.get_general_account()
        return general.balance > Decimal(amount)
    
    @staticmethod
    @db_transaction.atomic
    def cash_in(amount: Decimal, purpose: str = ""):
        amount = Decimal(amount)
        general = ManageAccounts.get_general_account()
        general.balance += amount
        general.save()

        Transaction.objects.create(
            from_account=None,
            to_account=general,
            type="IN",
            amount=amount,
            purpose=purpose or "Cash In to General Account"
        )

    @staticmethod
    @db_transaction.atomic
    def cash_out(amount: Decimal, purpose: str = ""):
        amount = Decimal(amount)
        general = ManageAccounts.get_general_account()
        if general.balance < amount:
            raise ValidationError("Insufficient balance in general account.")
        general.balance -= amount
        general.save()

        Transaction.objects.create(
            from_account=general,
            to_account=None,
            type="OUT",
            amount=amount,
            purpose=purpose or "Cash Out from General Account"
        )

    @staticmethod
    @db_transaction.atomic
    def transfer(from_account: Account, to_account: Account, amount: Decimal, purpose: str = ""):
        if from_account.balance < amount:
            raise ValidationError("Insufficient balance to transfer.")

        from_account.balance -= amount
        from_account.save()

        to_account.balance += amount
        to_account.save()

        Transaction.objects.create(
            from_account=from_account,
            to_account=to_account,
            type="TRANSFER",
            amount=amount,
            purpose=purpose or f"Transferred from {from_account.name} to {to_account.name}"
        )

    @staticmethod
    @db_transaction.atomic
    def transfer_all_balance(from_account: Account, to_account: Account, purpose: str = ""):
        if from_account == to_account:
            raise ValidationError("Source and target accounts cannot be the same.")

        amount = from_account.balance
        if amount <= 0:
            raise ValidationError("No balance to transfer.")

        ManageAccounts.transfer(
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            purpose=purpose or "Transfer all balance to another account"
        )

        # Optionally update general flag
        if from_account.is_general:
            from_account.is_general = False
            from_account.save()
            to_account.is_general = True
            to_account.save()

    @staticmethod
    def get_monthly_summary(account:Account):
        from .models import Transaction  # adjust if needed

        now = datetime.now()
        current_year = now.year
        current_month = now.month

        summary = []
        final_improvement = 0

        for month in range(1, current_month + 1):
            start_date = timezone.make_aware(datetime(current_year, month, 1))
            if month == 12:
                end_date = timezone.make_aware(datetime(current_year + 1, 1, 1))
            else:
                end_date = timezone.make_aware(datetime(current_year, month + 1, 1))

            monthly_transactions = Transaction.objects.filter(
                timestamp__gte=start_date,
                timestamp__lt=end_date
            )
            # print(monthly_transactions.count())
            # print(monthly_transactions.filter(type='IN',to_account=account).count(),monthly_transactions.filter(type='OUT',to_account=account).count())
            monthly_cash_in = monthly_transactions.filter(type='IN',to_account=account).aggregate(total=Sum('amount'))['total'] or 0
            monthly_cash_out = monthly_transactions.filter(type='OUT',from_account=account).aggregate(total=Sum('amount'))['total'] or 0

            summary.append({
                "month": calendar.month_name[month],
                'cash_in':monthly_cash_in,
                'cash_out':monthly_cash_out
            })

            final_improvement += monthly_cash_in - monthly_cash_out

        return {
            "name": account.name,
            "balance": float(account.balance),
            "monthly": summary,
            "final_improvement": float(final_improvement)
        }

    @staticmethod
    def get_all_accounts_summary():
        all_accounts = Account.objects.all()
        return [ManageAccounts.get_monthly_summary(account) for account in all_accounts]
    
    @staticmethod
    def get_revenue_expense_profit_summary():
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        summary = []
        total_revenue = 0
        total_expenses = 0
        total_profit = 0

        for month in range(1, current_month + 1):
            start_date = timezone.make_aware(datetime(current_year, month, 1))
            if month == 12:
                end_date = timezone.make_aware(datetime(current_year + 1, 1, 1))
            else:
                end_date = timezone.make_aware(datetime(current_year, month + 1, 1))

            revenue = Transaction.objects.filter(
                type='IN',
                timestamp__gte=start_date,
                timestamp__lt=end_date
            ).aggregate(total=Sum('amount'))['total'] or 0

            expenses = Transaction.objects.filter(
                type='OUT',
                timestamp__gte=start_date,
                timestamp__lt=end_date
            ).aggregate(total=Sum('amount'))['total'] or 0

            profit = revenue - expenses

            summary.append({
                "month": calendar.month_name[month],
                "revenue": float(revenue),
                "expenses": float(expenses),
                "profit": float(profit)
            })

            total_revenue += revenue
            total_expenses += expenses
            total_profit += profit

        return {
            "monthly": summary,
            "total": {
                "revenue": float(total_revenue),
                "expenses": float(total_expenses),
                "profit": float(total_profit)
            }
        }

class DashBoard(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self,request):
        clients = Client.objects.all().order_by("-id")
        projects = Project.objects.all().order_by("-id")
        payments = ProjectPayment.objects.all().order_by("-id")
        expanses = ProjectExpanse.objects.all().order_by("-id")
        services = Service.objects.all()
        accounts = ManageAccounts.get_all_accounts_summary()
        accounts_overview = ManageAccounts.get_revenue_expense_profit_summary()


        result = {
            "status": "success",
            "data": {
                "clients" : [{
                    "clientId": client.id,
                    "name": client.name,
                    "phone": client.phone,
                    "address": client.address,
                    "website": client.website,
                    "page": client.page,
                    "isActive": client.is_active,
                    "created": client.created_at.strftime('%Y-%m-%d')
                } for client in clients],
                "projects": [{
                    "projectId": project.id if project else None,
                    "client": project.client.name,
                    "service": project.service.title if project else None,
                    "budget": project.budget if project else 0,
                    "startDate": project.start_date if project else None,
                    "deadline": project.deadline if project else None,
                    "isCompleted": project.is_completed if project else False
                } for project in projects],
                "payments": [{
                    "paymentId": payment.id if payment else None,
                    "project": payment.project.service.title if payment else None,
                    "payAmount": payment.amount if payment else 0,
                    "payTransId": payment.trans_id,
                    "payDetails": payment.details if payment else '',
                    "payDate": payment.date if payment else None
                } for payment in payments],
                "expanses": [{
                    "expanseId": expanse.id if expanse else None,
                    "project": expanse.project.service.title if expanse else None,
                    "expanseAmount": expanse.amount if expanse else 0,
                    "expanseTransId": expanse.trans_id if expanse else None,
                    "expanseDetails": expanse.details if expanse else '',
                    "expanseDate": expanse.date if expanse else None
                } for expanse in expanses],
                "services":[{
                    "service":service.id,
                    "title": service.title,
                    "created": service.created_at.strftime('%Y-%m-%d')
                } for service in services],

                "accounts":accounts,
                "accountsOverview": accounts_overview
                
            }
        }
        print(accounts)
        return Response(result)



class ServiceView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        services = Service.objects.all().values()
    
        return Response({
            "status": "success",
            "data": {
                "service":{
                    "id": service.id,
                    "title": service.title,
                    "created": service.created_at.strftime('%Y-%m-%d')
                } for service in services
            }
        })
    
    def post(self, request):
        title = request.data.get('title')
        if not title:
            return Response({"status": "error", "message": "Title is required"}, status=400)
        
        service = Service.objects.create(title=title)
        return Response({
            "status": "success",
            "data": {
                "service":{
                    "id": service.id,
                    "title": service.title,
                    "created": service.created_at.strftime('%Y-%m-%d')
                }
            }
        })
    
    def put(self, request, service_id):
        service = Service.objects.filter(id=service_id).first()
        if not service:
            return Response({"status": "error", "message": "Service not found"}, status=404)
        
        title = request.data.get('title')
        if title:
            service.title = title
            service.save()
        
        return Response({
            "status": "success",
            "data": {
                "id": service.id,
                "title": service.title
            }
        })
    
    def delete(self, request, service_id):
        service = Service.objects.filter(id=service_id).first()
        if not service:
            return Response({"status": "error", "message": "Service not found"}, status=404)
        
        service.delete()
        return Response({"status": "success", "message": "Service deleted successfully"})
    

class ClientView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        clients = Client.objects.all().values()
    
        return Response({
            "status": "success",
            "data": list(clients)
        })
    
    def post(self, request):
        print(request.data)
        name = request.data.get('name')
        phone = request.data.get('phone')
        address = request.data.get('address')
        website = request.data.get('website', '')
        page = request.data.get('page', '')
        is_active = request.data.get('is_active', True)

        #project
        is_project = request.data.get('isProject', False)
        service_id = request.data.get('service')
        budget = request.data.get('budget', 0)
        start_date = request.data.get('startDate')
        deadline = request.data.get('deadline')
        is_completed = request.data.get('projectCompleted', False)

        #payment
        is_payment = request.data.get('isPayment', False)
        pay_amount = request.data.get('payAmount', 0)
        pay_trans_id = request.data.get('payTransId',None)
        pay_date = request.data.get('payDate', timezone.now().date())
        pay_details = request.data.get('payDetails', '')

        #expanse
        is_expanse = request.data.get('isExpanse', False)
        expanse_amount = request.data.get('expanseAmount', 0)
        expanse_trans_id = request.data.get('expanseTransId',None)
        expanse_date = request.data.get('expanseDate', timezone.now().date())
        expanse_details = request.data.get('expanseDetails', '')
        
        if not name or not phone or not address:
            return Response({"status": "error", "message": "Name, phone, and address are required"}, status=400)
        

        if is_project and (not service_id or not start_date or not deadline):
            return Response({"status": "error", "message": "Project, amount, and details are required"}, status=400)

        if is_payment and (not pay_amount or not pay_trans_id or not pay_details or not is_project):
                return Response({"status": "error", "message": "Project, amount, and details are required"}, status=400)
        
        if is_expanse and (not expanse_amount or not expanse_trans_id or not expanse_details or not is_project):
                return Response({"status": "error", "message": "Project, amount, and details are required"}, status=400)
        
        client = Client.objects.create(
            name=name, 
            phone=phone, 
            address=address,
            website=website,
            page=page,
            is_active=is_active
        )

        project = None
        payment = None
        expanse = None
        if is_project and service_id and start_date and deadline:
            service = Service.objects.filter(id=service_id).first()
            if not service:
                return Response({"status": "error", "message": "Invalid service"}, status=400)
            
            project = Project.objects.create(
                client=client,
                service=service,
                budget=budget,
                start_date=start_date,
                deadline=deadline,
                is_completed=is_completed
            )
            
            if is_payment and pay_amount and pay_trans_id and pay_details:
                payment = ProjectPayment.objects.create(
                    project=project,
                    amount=pay_amount,
                    trans_id = pay_trans_id,
                    details=pay_details,
                    date=pay_date
                )
                
                purpose = f"New project started. {pay_details}. service:{project.service.title} & clien: {project.client.name} -> phone:{project.client.phone}"
                ManageAccounts.cash_in(amount=pay_amount,purpose=purpose)
            
            if is_expanse and expanse_amount and expanse_trans_id and expanse_details:
                expanse = ProjectExpanse.objects.create(
                    project=project,
                    amount=expanse_amount,
                    trans_id = expanse_trans_id,
                    details=expanse_details,
                    date=expanse_date
                )

                purpose = f"Project expense. {expanse_details}. service:{project.service.title} & clien: {project.client.name} -> phone:{project.client.phone}"
                ManageAccounts.cash_out(amount=pay_amount,purpose=purpose)

            

            
        return Response({
            "status": "success",
            "data": {
                "client" : {
                    "clientId": client.id,
                    "name": client.name,
                    "phone": client.phone,
                    "address": client.address,
                    "website": client.website,
                    "page": client.page,
                    "isActive": client.is_active,
                    "createdAt": client.created_at.strftime('%Y-%m-%d')
                },
                "project": {
                    "projectId": project.id if project else None,
                    "client": client.name,
                    "service": project.service.title if project else None,
                    "budget": project.budget if project else 0,
                    "startDate": project.start_date if project else None,
                    "deadline": project.deadline if project else None,
                    "isCompleted": project.is_completed if project else False
                } if project else None,
                "payment": {
                    "paymentId": payment.id if payment else None,
                    "project": payment.project.service.title if payment else None,
                    "payAmount": payment.amount if payment else 0,
                    "payTransId": payment.trans_id,
                    "payDetails": payment.details if payment else '',
                    "payDate": payment.date if payment else None
                } if payment else None,
                "expanse": {
                    "expanseId": expanse.id if expanse else None,
                    "project": expanse.project.service.title if expanse else None,
                    "expanseAmount": expanse.amount if expanse else 0,
                    "expanseTransId": expanse.trans_id if expanse else None,
                    "expanseDetails": expanse.details if expanse else '',
                    "expanseDate": expanse.date if expanse else None
                } if expanse else None
            }
        })
    
    def put(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({"status": "error", "message": "Client not found"}, status=404)
        
        name = request.data.get('name')
        phone = request.data.get('phone')
        address = request.data.get('address')
        website = request.data.get('website', '')
        page = request.data.get('page', '')
        is_active = request.data.get('is_active', True)
        
        if name:
            client.name = name
        if phone:
            client.phone = phone
        if address:
            client.address = address
        if website:
            client.website = website
        if page:
            client.page = page
        client.is_active = is_active
        
        client.save()
        
        return Response({
            "status": "success",
            "data": {
                "clientId": client.id,
                "name": client.name,
                "phone": client.phone,
                "address": client.address,
                "website": client.website,
                "page": client.page,
                "isActive": client.is_active,
                "createdAt": client.created_at.strftime('%Y-%m-%d')
            }
        })
    
    def delete(self, request, client_id):
        client = Client.objects.filter(id=client_id).first()
        if not client:
            return Response({"status": "error", "message": "Client not found"}, status=404)
        
        client.delete()
        return Response({"status": "success", "message": "Client deleted successfully"})
    
class ProjectView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        projects = Project.objects.all().values()
    
        return Response({
            "status": "success",
            "data": list(projects)
        })
    
    def post(self, request):
        print(request.data)
        client_id = request.data.get('clientId')
        service_id = request.data.get('service')
        budget = request.data.get('budget', None)
        start_date = request.data.get('startDate')
        deadline = request.data.get('deadline')
        is_completed = request.data.get('projectCompleted', False)

        #payment
        is_payment = request.data.get('isPayment', False)
        pay_amount = request.data.get('payAmount', 0)
        pay_trans_id = request.data.get('payTransId',None)
        pay_date = request.data.get('payDate', timezone.now().date())
        pay_details = request.data.get('payDetails', '')

        #expanse
        is_expanse = request.data.get('isExpanse', False)
        expanse_amount = request.data.get('expanseAmount', 0)
        expanse_trans_id = request.data.get('expanseTransId',None)
        expanse_date = request.data.get('expanseDate', timezone.now().date())
        expanse_details = request.data.get('expanseDetails', '')
        
        
        if not budget or not client_id or not service_id or not start_date or not deadline:
            return Response({"status": "error", "message": "Client, service, start date and deadline are required"}, status=400)
        
        client = Client.objects.filter(id=client_id).first()
        service = Service.objects.filter(id=service_id).first()
        
        if not client or not service:
            return Response({"status": "error", "message": "Invalid client or service"}, status=400)

        if is_payment and (not pay_amount or not pay_trans_id or not pay_details):
                return Response({"status": "error", "message": "Project, amount, and details are required"}, status=400)
        
        if is_expanse and (not expanse_amount or not expanse_trans_id or not expanse_details):
                return Response({"status": "error", "message": "Project, amount, and details are required"}, status=400)
        
        project = Project.objects.create(
            client=client,
            service=service,
            budget=budget,
            start_date=start_date,
            deadline=deadline,
            is_completed=is_completed
        )

        payment = None
        expanse = None
        
        if is_payment:
            payment = ProjectPayment.objects.create(
                project=project,
                amount=pay_amount,
                trans_id = pay_trans_id,
                details=pay_details,
                date=pay_date
            )
            
            purpose = f"New project started. {pay_details}. service:{project.service.title} & clien: {project.client.name} -> phone:{project.client.phone}"
            ManageAccounts.cash_in(amount=payment.amount,purpose=purpose)
            
        if is_expanse:
            expanse = ProjectExpanse.objects.create(
                project=project,
                amount=expanse_amount,
                trans_id = expanse_trans_id,
                details=expanse_details,
                date=expanse_date
            )

            purpose = f"Project expense. {expanse_details}. service:{project.service.title} & clien: {project.client.name} -> phone:{project.client.phone}"
            ManageAccounts.cash_out(amount=expanse.amount,purpose=purpose)

        return Response({
            "status": "success",
            "data": {
                "project":{
                    "projectId": project.id,
                    "client": project.client.name,
                    "service": project.service.title,
                    "budget": project.budget,
                    "startDate": project.start_date,
                    "deadline": project.deadline,
                    "isCompleted": project.is_completed
                },
                "payment": {
                    "paymentId": payment.id if payment else None,
                    "project": payment.project.service.title if payment else None,
                    "payAmount": payment.amount if payment else 0,
                    "payTransId": payment.trans_id,
                    "payDetails": payment.details if payment else '',
                    "payDate": payment.date if payment else None
                } if payment else None,
                "expanse": {
                    "expanseId": expanse.id if expanse else None,
                    "project": expanse.project.service.title if expanse else None,
                    "expanseAmount": expanse.amount if expanse else 0,
                    "expanseTransId": expanse.trans_id if expanse else None,
                    "expanseDetails": expanse.details if expanse else '',
                    "expanseDate": expanse.date if expanse else None
                } if expanse else None
            }
        })
    
    def put(self, request, project_id):
        project = Project.objects.filter(id=project_id).first()
        if not project:
            return Response({"status": "error", "message": "Project not found"}, status=404)
        
        client_id = request.data.get('client')
        service_id = request.data.get('service')
        budget = request.data.get('budget', 0)
        start_date = request.data.get('startDate')
        deadline = request.data.get('deadline')
        is_completed = request.data.get('projectCompleted', False)
        
        if client_id:
            client = Client.objects.filter(id=client_id).first()
            if not client:
                return Response({"status": "error", "message": "Invalid client"}, status=400)
            project.client = client
        
        if service_id:
            service = Service.objects.filter(id=service_id).first()
            if not service:
                return Response({"status": "error", "message": "Invalid service"}, status=400)
            project.service = service
        
        if budget is not None:
            project.budget = budget
        if start_date:
            project.start_date = start_date
        if deadline:
            project.deadline = deadline
        project.is_completed = is_completed
        
        project.save()
        
        return Response({
            "status": "success",
            "data": {
                "projectId": project.id,
                "client": project.client.name,
                "service": project.service.title,
                "budget": project.budget,
                "startDate": project.start_date,
                "deadline": project.deadline,
                "isCompleted": project.is_completed
            }
        })
    
    def delete(self, request, project_id):
        project = Project.objects.filter(id=project_id).first()
        if not project:
            return Response({"status": "error", "message": "Project not found"}, status=404)
        
        project.delete()
        return Response({"status": "success", "message": "Project deleted successfully"})


class ProjectExpanseView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        expanses = ProjectExpanse.objects.all().values()
    
        return Response({
            "status": "success",
            "data": list(expanses)
        })
    
    def post(self, request):
        expanse = None
        try:
            project_id = request.data.get('projectId')
            amount = request.data.get('expanseAmount', 0)
            trans_id = request.data.get('expanseTransId',None)
            date = request.data.get('expanseDate', timezone.now().date())
            details = request.data.get('expanseDetails', '')

            if not project_id or not amount or not details or not trans_id:
                return Response({"status": "error", "message": "Project, amount, and details are required"}, status=400)
            
            project = Project.objects.filter(id=project_id).first()
            if not project:
                return Response({"status": "error", "message": "Invalid project"}, status=400)  
            
            if date:
                try:
                    date = timezone.datetime.strptime(date, '%Y-%m-%d').date()
                except ValueError:
                    return Response({"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}, status=400)
            
            if not ManageAccounts.has_sufficient_expense_amount(amount):
                return Response({"status": "error", "message": "Insufficient balance in general account."}, status=400)
                
            expanse = ProjectExpanse.objects.create(
                project=project,
                amount=amount,
                trans_id = trans_id,
                details=details,
                date=date
            )

            purpose = f"Project expense. {details}. service:{project.service.title} & clien: {project.client.name} -> phone:{project.client.phone}"
            ManageAccounts.cash_out(amount=amount,purpose=purpose)
            
            return Response({
                "status": "success",
                "data": {
                    "expanse":{
                        "expanseId": expanse.id,
                        "client": expanse.project.client.name,
                        "project": expanse.project.service.title,
                        "expanseAmount": expanse.amount,
                        "expanseTransId": expanse.trans_id,
                        "expanseDetails": expanse.details,
                        "expanseDate": expanse.date
                    }
                }
            })
        except Exception as e:
            if expanse:
                expanse.delete()

            return Response({"status": "error", "message": "Something went wrong."}, status=400)
    

    def put(self, request, expanse_id):
        expanse = ProjectExpanse.objects.filter(id=expanse_id).first()
        if not expanse:
            return Response({"status": "error", "message": "Expanse not found"}, status=404)
        
        project_id = request.data.get('projectId')
        amount = request.data.get('expanseAmount', 0)
        trans_id = request.data.get('expanseTransId',None)
        date = request.data.get('expanseDate', timezone.now().date())
        details = request.data.get('expanseDetails', '')

        if project_id:
            project = Project.objects.filter(id=project_id).first()
            if not project:
                return Response({"status": "error", "message": "Invalid project"}, status=400)
            expanse.project = project

        if amount is not None:
            new_amount = amount
            old_amount = expanse.amount

            amount_difference = new_amount - old_amount

            if new_amount != old_amount:
                expanse.amount = new_amount

                purpose = f"Project expense edited {old_amount} to {new_amount}. {details}. service:{project.service.title} & clien: {project.client.name} -> phone:{project.client.phone}"
                if amount_difference > 0:
                    ManageAccounts.cash_out(amount=amount_difference,purpose=purpose)
                else:
                    ManageAccounts.cash_in(amount=abs(amount_difference),purpose=purpose)
        
        if trans_id:
            expanse.trans_id = trans_id
        
        if details:
            expanse.details = details

        if date:
            try:
                expanse.date = timezone.datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                return Response({"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        expanse.is_edited = True
        expanse.save()

        return Response({
            "status": "success",
            "data": {
                "expanse":{
                    "expanseId": expanse.id,
                    "client": expanse.project.client.name,
                    "project": expanse.project.service.title,
                    "expanseAmount": expanse.amount,
                    "expanseTransId": expanse.trans_id,
                    "expanseDetails": expanse.details,
                    "expanseDate": expanse.date
                }
            }
        })
    
    def delete(self, request, expanse_id):
        expanse = ProjectExpanse.objects.filter(id=expanse_id).first()
        if not expanse:
            return Response({"status": "error", "message": "Expanse not found"}, status=404)
        
        expanse.delete()
        return Response({"status": "success", "message": "Expanse deleted successfully"})
    

class ProjectPaymentView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        payments = ProjectPayment.objects.all().values()
    
        return Response({
            "status": "success",
            "data": list(payments)
        })
    
    def post(self, request):
        project_id = request.data.get('projectId')
        amount = request.data.get('payAmount', 0)
        trans_id = request.data.get('payTransId',None)
        date = request.data.get('payDate', timezone.now().date())
        details = request.data.get('payDetails', '')

        print(project_id,amount,details,trans_id,not project_id or not amount or not details or not trans_id)
        if not project_id or not amount or not details or not trans_id:
            return Response({"status": "error", "message": "Project, amount, and details are required"}, status=400)
        
        project = Project.objects.filter(id=project_id).first()
        if not project:
            return Response({"status": "error", "message": "Invalid project"}, status=400)  
        
        if date:
            try:
                date = timezone.datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                return Response({"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}, status=400)
        
        payment = ProjectPayment.objects.create(
            project=project,
            amount=amount,
            trans_id = trans_id,
            details=details,
            date=date
        )

        purpose = f"Project payment. {details}. service:{project.service.title} & clien: {project.client.name} -> phone:{project.client.phone}"
        ManageAccounts.cash_in(amount=amount,purpose=purpose)

        return Response({
            "status": "success",
            "data": {
                "payment":{
                    "paymentId": payment.id,
                    "client": payment.project.client.name,
                    "project": payment.project.service.title,
                    "payAmount": payment.amount,
                    "payTransId": payment.trans_id,
                    "payDetails": payment.details,
                    "payDate": payment.date
                }
            }
        })

    def put(self, request, payment_id):
        payment = ProjectPayment.objects.filter(id=payment_id).first()
        if not payment:
            return Response({"status": "error", "message": "Payment not found"}, status=404)
        
        project_id = request.data.get('projectId')
        amount = request.data.get('payAmount', 0)
        trans_id = request.data.get('payTransId',None)
        date = request.data.get('payDate', timezone.now().date())
        details = request.data.get('payDetails', '')

        if project_id:
            project = Project.objects.filter(id=project_id).first()
            if not project:
                return Response({"status": "error", "message": "Invalid project"}, status=400)
            payment.project = project

        if amount is not None:
            new_amount = amount
            old_amount = payment.amount

            amount_difference = new_amount - old_amount

            if new_amount != old_amount:
                payment.amount = new_amount

                purpose = f"Project payment edited {old_amount} to {new_amount}. {details}. service:{project.service.title} & clien: {project.client.name} -> phone:{project.client.phone}"
                if amount_difference < 0:
                    ManageAccounts.cash_out(amount=abs(amount_difference),purpose=purpose)
                else:
                    ManageAccounts.cash_in(amount=amount_difference,purpose=purpose)

        
        if trans_id:
            payment.trans_id = trans_id
        
        if details:
            payment.details = details

        if date:
            try:
                payment.date = timezone.datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                return Response({"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}, status=400)

        payment.is_edited = True
        payment.save()

        return Response({
            "status": "success",
            "data": {
                "payment":{
                    "paymentId": payment.id,
                    "client": payment.project.client.name,
                    "project": payment.project.service.title,
                    "payAmount": payment.amount,
                    "payTransId": payment.trans_id,
                    "payDetails": payment.details,
                    "payDate": payment.date
                }
            }
        })