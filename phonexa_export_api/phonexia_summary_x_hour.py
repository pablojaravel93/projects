import hashlib
import datetime
import requests

signData = {
    'date': datetime.datetime.now().strftime('%d.%m.%Y'), # Current Date in format d.m.Y
    'userId': '1008', # Id of user assigned to API ID
    'component': 'lms', # One of Component list
    'menuItemId': 'report::summarypublisherbyhour::index', # one of menuItemId
    'category': '2' # one of Category List
}

signDataSorted = dict(sorted(signData.items()))

signature = hashlib.md5(
    (hashlib.md5('|'.join(signDataSorted.values()).encode('utf-8')).hexdigest() + '|0c356624bbc63c788067623566eab').encode('utf-8')
).hexdigest()

print(signature)


#Report URL
url ="https://cp-inst528-client.phonexa.com/export/api?menuItemId=report::summarypublisherbyhour::index&apiId=F7524164CD1D4380A5993362E5F583AC&signature="+signature+"&component=lms"
print(url)

# response = requests.get(url)

# print(response.headers.get)