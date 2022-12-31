import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header

def send_mail(to, subject, message):
  password = os.environ['EMAIL_PASSWORD']
  mail = MIMEText(message, 'plain', 'utf-8')
  mail['Subject'] = Header(subject, 'utf-8')

  server = smtplib.SMTP('smtp.gmail.com')
  server.starttls()
  server.login("booksriver.noreply@gmail.com", password)
  server.sendmail("booksriver.noreply@gmail.com", to, mail.as_string())
  server.quit()