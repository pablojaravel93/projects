import hashlib
import datetime
import requests
import pytz

signData = {
    'date': datetime.datetime.now().strftime('%d.%m.%Y'), # Current Date in format d.m.Y
    'userId': '1014', # Id of user assigned to API ID
    'component': 'lms', # One of Component list
    'menuItemId': 'report::lead::index', # one of menuItemId
    'category': '1' # one of Category List
}

signDataSorted = dict(sorted(signData.items()))

signature = hashlib.md5(
    (hashlib.md5('|'.join(signDataSorted.values()).encode('utf-8')).hexdigest() + '|82272d81f6dc0caaa1830025cf').encode('utf-8')
).hexdigest()


#set date parameter
timezone = pytz.timezone('America/Los_Angeles')
today = datetime.datetime.now(timezone).strftime("%m/%d/%Y")
date_parameter = today+" 00:00:00 - "+today+" 23:59:59"

#Report URL
url = "https://cp-inst528-client.phonexa.com/export/api?menuItemId=report::lead::index&apiId=2872DEB47BAD420C9BF9B270C912DB1B&signature="+signature+"&component=lms&searchForm[creationDatetime]="+date_parameter

print(signature)

print(url)

# response = requests.get(url)

# print(response.headers.get)