from celery import shared_task
from .sender import PhoneSender

@shared_task(
    bind=True,
    queue="scheduler",
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
)
def trigger_call_task(self, phone_number):
    sender = PhoneSender()
    return sender.click_to_call(phone_number)