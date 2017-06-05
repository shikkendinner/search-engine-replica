from bottle import route, error, run, static_file, request, response, redirect, app, post 
from bs4 import BeautifulSoup
import redis
import pickle
import math

from oauth2client.client import flow_from_clientsecrets
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from httplib2 import Http

from beaker.middleware import SessionMiddleware

#We need to add SessionMiddleware module as a part of our bottle applet
#Store the session object within the cookies being sent, and set cookie expiry such that it expires in a minute of no use at all
#Set auto parameter such that once session is accessed, any modifications are saved in the cookie
session_opts = {
		'session.type': 'cookie',
		'session.auto': True,
		'session.cookie_expires': 300,
		'session.validate_key': 'puddle'
}

app = SessionMiddleware(app(), session_opts)

#A redis database of users and their list of top 20 keywords that they have recently searched
rServer = redis.Redis('localhost')

#This GET request provides the base query page and if parameters exist, will provide the result page
@route('/')
def showPage():
	#Check if we are in anonymous or signed in mode
	anonMode = True
	session = request.environ.get('beaker.session')
	userAddress = None
	#If a user is logged in, get the email address
	if 'credentials' in session:
		anonMode = False
		#Access credentials from the session storage object
		credentials = session['credentials']
		http = credentials.authorize(Http())
		
		#Get email address using credential object
		usersService = build('oauth2', 'v2', http=http)
		userDocument = usersService.userinfo().get().execute()
		userAddress = userDocument['email']
	
	#Checks whether a phrase was searched or just loading the query page
	#Also if a phrase was searched, it makes sure the phrase is not just blank spaces
	if 'keywords' not in request.query or request.query.keywords.isspace():
		#Access the Query Page html file
		#BeautifulSoup allows us to parse and modify the html file
		with open('../frontend/html/querypage.html', 'r+') as htmlQuery:
			soupQuery = BeautifulSoup(htmlQuery.read())
		
		#Check if a user is signed in or not
		if not anonMode:
			#Places userAddress at the top right and replaces Sign-In with Sign-Out
			loginTitle = soupQuery.find(id='loginTitle')
			loginTitle.string = userAddress

			loginButton = soupQuery.find(id='logInButton')
			loginButton.string = 'Sign-Out'			

			#Checks whether the user has a list of keywords and if the list is empty		
			if rServer.llen(userAddress) > 0:			
				#Allows us to modify the table element
				historyTable = soupQuery.find(id='history')
				count = 0
			
				#Goes through all top 20 keywords and adds them to the table
				for kwd in rServer.lrange(userAddress, 0, -1):
					count+=1

					newRowTag = soupQuery.new_tag('tr')
					newRowDataPosition = soupQuery.new_tag('td')
					newRowDataWord = soupQuery.new_tag('td')
				
					newRowDataPosition.string = str(count)
					newRowTag.append(newRowDataPosition)
					newRowDataWord.string = kwd
					newRowTag.append(newRowDataWord)

					historyTable.append(newRowTag)
		else:
			#Since the user is anonymous, revoke the ability to store most searched keywords and notify user that they cannot use this feature
			historyTable = soupQuery.find(id='history')
			warningTag = soupQuery.new_tag('strong')
			warningTag.string = '*This feature is not available unless you sign-in using your google account*'
			historyTable.replace_with(warningTag)

		#Adds the QueryPage.html code and any modifications and writes it to an output file that will be displayed to the user
		with open('../frontend/html/output.html', 'w') as htmlOutput:
			htmlOutput.write(soupQuery.prettify())				
	else:
		#A dictionary to hold the keywords and their count from user input
		inputWords = {}

		#Access the Result Page html file
		#BeautifulSoup allows us to parse and modify the html file
		with open('../frontend/html/resultpage.html', 'r+') as htmlResult:
			soupResult = BeautifulSoup(htmlResult.read())
		
		#Modifies string to lowercase, strips all extra spaces
		#Parse the user inputted string
		parsed = request.query.keywords.lower().split()

		#Joins parsed string to show user what was searched in output
		cleanText = " ".join(parsed)

		#Check if user is in anonymous mode or not
		if not anonMode:
			#Places userAddress at the top right and replaces Sign-In with Sign-Out
			loginTitle = soupResult.find(id='loginTitle')
			loginTitle.string = userAddress

			loginButton = soupResult.find(id='logInButton')
			loginButton.string = 'Sign-Out'

			#Iterates through all the words from the string, adds their count to inputWords dictionary
			#Updates the top 20 keywords searched such that the list is in order of most recently searched
			for word in parsed:
				if word in rServer.lrange(userAddress, 0, -1):
					rServer.lrem(userAddress, word, 0)
					rServer.lpush(userAddress, word)
				else:
					if rServer.llen(userAddress) == 20:
						rServer.rpop(userAddress)

					rServer.lpush(userAddress, word)

				#if word in inputWords:
					#inputWords[word] += 1
				#else:
					#inputWords[word] = 1
		#else:
			#Iterates through all the words from the string, adds their count to inputWords dictionary
			#for word in parsed:
				#if word in inputWords:
					#inputWords[word] += 1
				#else:
					#inputWords[word] = 1
		
		#Add text to search bar to show what is being searched for
		textInBar = soupResult.find(id='searchArea')
		textInBar['value'] = request.query.keywords	
		
		#Add text to indicate what was searched for
		#textOfPhrase = soupResult.find(id='text')
		#textOfPhrase.string = 'Search for "' + cleanText + '"'
		
		#Provides access to the HTML results table
		#resultTable = soupResult.find(id='results')

		#Iterate through all words from the phrase and add them to the table with their counts
		#for key, value in inputWords.iteritems():
			#newRowTag = soupResult.new_tag('tr')
			#newRowDataWord = soupResult.new_tag('td')
			#newRowDataCount = soupResult.new_tag('td')

			#newRowDataWord.string = key
			#newRowTag.append(newRowDataWord)
			#newRowDataCount.string = str(value)
			#newRowTag.append(newRowDataCount)

			#resultTable.append(newRowTag)

		#Adds the ResultPage.html code and any modifications and writes it to an output file that will be displayed to the user
		with open('../frontend/html/output.html', 'w') as htmlOutput:
			htmlOutput.write(soupResult.prettify())

	response = static_file('output.html', root='../frontend/html/')
	response.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
	return response

#Facilitates the sign-in and sign-off process for google accounts
@route('/googleAction')
def signInOut():
	with open('../frontend/html/output.html', 'r+') as htmlOutput:
		soupOutput = BeautifulSoup(htmlOutput.read())

	buttonTitle = soupOutput.find(id='logInButton').string.strip()

	#Decide whether user is signed in or not
	if buttonTitle == 'Sign-In':
		flow = flow_from_clientsecrets('clientsecrets_in_puddle.json', 
										scope='https://www.googleapis.com/auth/plus.me https://www.googleapis.com/auth/userinfo.email', 
										redirect_uri='http://localhost:8080/initSession')

		uri = flow.step1_get_authorize_url()
		redirect(str(uri))
	else:
		#Invalidate the session, such that a new one is created without a credentials object
		session = request.environ.get('beaker.session')
		session.invalidate()
		#Go back to the query page
		redirect('http://localhost:8080')
		
@route('/initSession')
def initSession():
	#Attain authorization code	
	code = request.query.code
	#Provides us with the flow object that allows us to get the credentials to access the user data
	flow = flow_from_clientsecrets('clientsecrets_in_puddle.json', 
					scope='https://www.googleapis.com/auth/plus.me https://www.googleapis.com/auth/userinfo.email', 
					redirect_uri='http://localhost:8080/initSession')
	#This object has tokens that are used to allow access to user data
	credentials = flow.step2_exchange(code)

	#Add credentials to our sessionManager Object
	#Save the object as it will now store the credentials
	session = request.environ.get('beaker.session')
	session['credentials'] = credentials
	session.save()

	#Head back to the query page
	redirect('http://localhost:8080')

@post('/getURLs')
def getURLs():
		#Map all the words with the crawler and page rank database		
		allWords = request.forms.get('allWords')
		pageNum = request.forms.get('pageNum')

		docID = getDocIdList(allWords)
		
		numPages = int(math.ceil(float(len(docID[0]+docID[1]))/5))

		if numPages:
			sortedDocs = getURLlist(docID)

			partOfList = 5*int(pageNum)

			return {'result': numPages, 'urls': sortedDocs[0][partOfList-5:partOfList], 'titles': sortedDocs[1][partOfList-5:partOfList]}
		else:
			#Return the fact that no results are available
			return {'result': numPages, 'urls': [], 'titles': []}

def getDocIdList(keywords):
	keywords = keywords.split()
	tempLists = []

	for word in keywords:
		if rServer.hget('wordTodoc', word) is None:
			tempLists.append([])
		else:
			tempLists.append(pickle.loads(rServer.hget('wordTodoc', word)))	

	commonIDs = list(reduce(findCommon, tempLists))

	uncommonIDs = list(set(reduce(lambda x, y: list(x)+list(y), tempLists)).difference(commonIDs))

	return (commonIDs, uncommonIDs)

def findCommon(fList, sList):
	if len(fList) == 0:
		return sList
	elif len(sList) == 0:
		return fList
	else:
		return fList.intersection(sList)

def getURLlist(docID):
	sortedDocURLcommon = []
	sortedDocURLuncommon = []

	if len(docID[0]):
		#FIRST DO IT FOR THE COMMON IDs
	
		#get the out of order docIDtoPageRank conversion
		docIDtoPageRank = {key:rServer.hget('page_rank_dict', key) for key in docID[0]}
		#sorted doc IDs using pageRank score for comparison			
		sortedDocID = sorted(docIDtoPageRank, key=docIDtoPageRank.__getitem__, reverse=True)
		#convert IDs to URLs
		sortedDocURLcommon = [rServer.hget('Document_index_dict', key) for key in sortedDocID]

		#get the missing doc IDs that are not in the sorted list due to a zero page rank
		noRankID = set(docID[0]).difference(sortedDocID)
		noRankURL = [rServer.hget('Document_index_dict', key) for key in noRankID]

		for url in noRankURL:
			sortedDocURLcommon.append(url)
	
	if len(docID[1]):
		#NOW FOR THE UNCOMMON IDs

		#get the out of order docIDtoPageRank conversion
		docIDtoPageRank = {key:rServer.hget('page_rank_dict', key) for key in docID[1]}
		#sorted doc IDs using pageRank score for comparison			
		sortedDocID = sorted(docIDtoPageRank, key=docIDtoPageRank.__getitem__, reverse=True)
		#convert IDs to URLs
		sortedDocURLuncommon = [rServer.hget('Document_index_dict', key) for key in sortedDocID]

		#get the missing doc IDs that are not in the sorted list due to a zero page rank
		noRankID = set(docID[1]).difference(sortedDocID)
		noRankURL = [rServer.hget('Document_index_dict', key) for key in noRankID]

		for url in noRankURL:
			sortedDocURLuncommon.append(url)

	#Finally put the two together such that the common urls between all or atleast some of the keywords are first
	sortedDocURL = sortedDocURLcommon + sortedDocURLuncommon

	#Get every URL's title and store it
	sortedDocTitle = []

	for URL in sortedDocURL:
		sortedDocTitle.append(rServer.hget('Document_index_title', URL))

	return (sortedDocURL, sortedDocTitle)

#All errors will be redirected to the error.html template page
@error(404)
def error404(error):
	return static_file('errorpage.html', root='../frontend/html/')

@error(405)
def error405(error):
	return static_file('errorpage.html', root='../frontend/html/')
	
#Provides access to static image files to load the logo and favicon
@route('/images/<filename>')
def getImage(filename):
	return static_file(filename, root='../frontend/images/')

run(app=app, host='localhost', port=8080, debug=True)
