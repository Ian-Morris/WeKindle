from flask import current_app, render_template
from flask.ext.mail import Message
from extensions import celery, mail

@celery.task
def send_async_email(msg):
    mail.send(msg)

def send_email(to, subject, template, **kwargs):
    app = current_app._get_current_object()
    msg = Message(app.config['FLASKY_MAIL_SUBJECT_PREFIX'] + ' ' + subject,
                  sender=app.config['FLASKY_MAIL_SENDER'], recipients=[to])
    msg.body = render_template(template + '.txt', **kwargs)
    msg.html = render_template(template + '.html', **kwargs)
    with app.open_resource("test.mobi") as fp:
        msg.attach("test.mobi", "application/x-mobipocket-ebook", fp.read())
    send_async_email.delay(msg)


