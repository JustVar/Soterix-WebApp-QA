def send_mail(from_address="person@example.com", to_address=["person@example.com"], subject="TMS API AutomationTesting Status", body="TMS API AutomationTesting Status", file_attachment=""):
    import os
    import smtplib
    from email import encoders
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    recipients = ["person@example.com", "person@example.com"]#, "person@example.com",
                  #"person@example.com",
                  #"person@example.com",
                  #"person@example.com",
                  #"person@example.com",
                  #"person@example.com",
                  #"person@example.com",
                  #"person@example.com"]
    to_address = recipients

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "password.txt")) as fl:
        pssd = fl.read()
    #pssd = "ecnmpmxbjudwipoj"
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.login(from_address, pssd)
    msg = MIMEMultipart()

    msg['From'] = from_address
    msg['To'] = ', '.join(to_address)
    msg['Subject'] = subject

    # Attach HTML content
    msg.attach(MIMEText(body, 'html'))
    if file_attachment:
        filename = os.path.basename(file_attachment)
        attachment = open(file_attachment, "rb")

        part = MIMEBase('application', 'octet-stream')
        part.set_payload((attachment).read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', "attachment; filename= %s" % filename)
        msg.attach(part)
    server.sendmail(from_address, to_address, msg.as_string())
    server.close()
