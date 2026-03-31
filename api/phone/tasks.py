from .sender import PhoneSender

def trigger_call_task(self, phone_number):
    sender = PhoneSender()
    return sender.click_to_call(phone_number)