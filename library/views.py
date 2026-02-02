from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Author, Book, Member, Loan
from .serializers import AuthorSerializer, BookSerializer, MemberSerializer, LoanSerializer, TopActiveMemberSerializer
from rest_framework.decorators import action
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from .tasks import send_loan_notification

class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer

    def get_queryset(self):
        return Book.objects.select_related('author')

    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)
    
    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset=queryset)
        if page is not None:
            serializer = self.get_serializer(page,many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset,many=True)
        return Response(serializer.data)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, methods=['get'], url_path='top-active')
    def top_active(self, request):
        top_members = Member.objects.select_related('user').annotate(
            active_loans_count=Count('loans', filter=Q(loans__is_returned=False))
        ).filter(
            active_loans_count__gt=0
        ).order_by('-active_loans_count')[:5]

        serializer = TopActiveMemberSerializer(top_members, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True,methods=["POST"])
    def extend_due_date(self,request,**kwargs):
        try:
            loan = self.get_object()
        except Loan.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND,data="Loan not found")
        
        additional_days = request.data.get("additional_days")
        if not additional_days or additional_days < 0:
            return Response(status=status.HTTP_400_BAD_REQUEST,data="Incorrect additional number of days provided")

        
        overdue_days = (loan.due_date - timezone.now().date()).days
        if overdue_days < 0:
            return Response(status=status.HTTP_400_BAD_REQUEST,data="Loan is overdue")

        loan.due_date = loan.due_date +timedelta(days=additional_days)
        loan.save(update_fields=["due_date"])

        serializer = self.get_serializer(loan)
        return Response(data=serializer.data)
        

