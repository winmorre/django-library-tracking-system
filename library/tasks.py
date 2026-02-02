from celery import shared_task, group
from .models import Loan
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass

@shared_task
def check_overdue_loans():
    todays_date = timezone.now().date()
    over_due_loans = Loan.objects.select_related("member__user","book").filter(is_returned=False, due_date__lt=todays_date)

    if not over_due_loans.exists():
        return
    
    group_task = group([send_email_to_members.si(ov.member.user.username,ov.book.title,ov.member.user.email) for ov in over_due_loans])

    group_task.apply_async()


@shared_task
def send_email_to_members(member_name, book_title,member_email):
    send_mail(
        subject="Book Loan past due date",
        message=f"Hello {member_name}, \n\n The due date for the loaned book {book_title} is overdue!",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[member_email],
        fail_silently=False
    )

