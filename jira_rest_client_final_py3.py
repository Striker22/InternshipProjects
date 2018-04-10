from jira import JIRA,JIRAError
import json
from prettytable import PrettyTable
import pymysql.cursors
import pandas as pd
import os

# Using basic authentication for using the resources of the resource owner.
# username and password is sent using base64 encoding.
def basicAuthentication():
	option = {'server':'https://example123456.atlassian.net'}
	# jira_username = raw_input("Enter the username: ")
	# jira_password = getpass("Enter the password: ")
	jira_username = 'admin'
	jira_password = '12345678'
	try:
		jira = JIRA(basic_auth=(jira_username,jira_password),options=option)
		print("Authentication Sucessfull")
		return (True,jira)		
	except JIRAError as e:
		print(e)
		error = jiraErrorinfo(e.status_code)
		return (False,error)

def jiraErrorinfo(statusCode):
	if statusCode == 401:
		return ("The Authentication Details You Provided is Invalid")
	elif statusCode == 200:
		return ("It Worked")
	elif statusCode == 201:
		return ("The resource was created successfully. The body should contain a “links” map with a “self” field that contains the new URL to access the created resource. Alternatively, the URL will be in the “Location” header")
	elif statusCode == 202:
		return ("When using test_auth=true, this response code indicates that the auth_token is valid.")
	elif statusCode == 204:
		return ("The request succeeded and the response does not contain any content.")
	elif statusCode == 400:
		return ("The request was invalid. You may be missing a required argument or provided bad data. An error message will be returned explaining what happened.")
	elif statusCode == 403:
		return ("You don’t have permission to complete the operation or access the resource.")
	elif statusCode == 404:
		return ("You requested an invalid method")
	elif statusCode == 405:
		return ("The method specified in the Request-Line is not allowed for the resource identified by the Request-URI. (used POST instead of PUT)")
	elif statusCode == 429:
		return ("Too Many Requests: You have exceeded the rate limit")
	elif statusCode == 500:
		return ("Something is wrong on our end. We’ll investigate what happened. Feel free to contact us.")
	elif statusCode == 503:
		return ("The method you requested is currently unavailable (due to maintenance or high load).")

def projectDetails(jira):
	proList = jira.projects()
	print("Total Number of Projects In An Account: %s" %len(proList))
	return proList

def printProjectDetails(jira, list):
	t = PrettyTable(['ID','Key','Name','Type','Description','Lead','Active'])
	for i in list:
		info = jira.project(i)
		if info.description is not "":
			t.add_row([i.id,i.key,i.name,i.projectTypeKey,info.description,info.lead.displayName,info.lead.active])
		else:
			t.add_row([i.id,i.key,i.name,i.projectTypeKey,'No Description',info.lead.displayName,info.lead.active])
	print(t)

def binarySearch(key,list):
	start = 0
	end = len(list)-1
	while (start <= end):
		mid = int(((end-start)/2) + start)
		# print(mid)
		if key in list[mid].name:
			return mid
		elif list[mid].name > key:
			end = mid-1
		else:
			start = mid+1
	return (-1)

def queryExecution(conn,idWebRtc):
	if idWebRtc == False:
		query = "select * from vega.tblSessWebRtc inner join vega.tblBugReportStats on (vega.tblSessWebRtc.idtblSessWebRtc = vega.tblBugReportStats.sessWebRtcId) inner join vega.tblFbOutput on (vega.tblBugReportStats.fbOutputId = vega.tblFbOutput.idFbOutput) inner join vega.tblFBoutputDtls on (vega.tblFbOutput.idFbOutput = vega.tblFBoutputDtls.fboId and fbpTextVal is not NULL)"
	else:
		query = "select * from (vega.tblSessWebRtc inner join vega.tblBugReportStats on (vega.tblSessWebRtc.idtblSessWebRtc = vega.tblBugReportStats.sessWebRtcId) inner join vega.tblFbOutput on (vega.tblBugReportStats.fbOutputId = vega.tblFbOutput.idFbOutput) inner join vega.tblFBoutputDtls on (vega.tblFbOutput.idFbOutput = vega.tblFBoutputDtls.fboId and fbpTextVal is not NULL)) where idtblSessWebRtc >" + str(idWebRtc)
	
	df = pd.read_sql(query,conn)
	return df

def insertDatabase(conn,value):
	try:
		# print(value)
		cur = conn.cursor()
		query = 'update vega.tblConfigure set value ='+str(value)+" where searchKey = 'BUG_REPORT_LAST_READ_RECORD_ID'"
		cur.execute(query)
		conn.commit()
	except pymysql.Error as e:
		print(e)
		cur.rollback()

def insertBugReport(jira,df,pKey):
	# Inserting the issue in the jira accnt, as per the specified format.
	# Header of the bug report is of the form:
	# Bug_Report_SessionID_SessKey_Name_IsHost/GlassUser_Video/Audio_Problem
	# print("Project Key is: %s" %(pKey))
	for row in df.itertuples(index = False,name='df'):
		sessionUserId = getattr(row,'sessUserId')
		sessionKey = getattr(row,'sessKey')
		userName = getattr(row,'name')
		isHost = getattr(row,'isHost')
		isGlassUser = getattr(row,'isGlassUser')
		desc = getattr(row,'fbpTextVal')

		# Below variables stores the stats of the session in json format.
		ptV = getattr(row,'ptVideo')
		ptA = getattr(row,'ptAudio')
		ptWhite = getattr(row,'ptWhiteboard')
		ptLive = getattr(row,'ptLiveStream')
		ptScreen = getattr(row,'ptScreen')
		ptVideoAsset = getattr(row,'ptVideoAssetStream')
		ptLocal = getattr(row,'ptLocal')
		
		if isHost == 1 and isGlassUser == 0:
			Summary = "BugReport_"+str(sessionUserId)+"_"+str(sessionKey)+"_"+str(userName)+"_"+"Host"
		elif isHost == 0 and isGlassUser ==1:
			Summary = "BugReport_"+str(sessionUserId)+"_"+str(sessionKey)+"_"+str(userName)+"_"+"GlassUser"
		elif isHost == 0 and isGlassUser == 0:
			Summary = "BugReport_"+str(sessionUserId)+"_"+str(sessionKey)+"_"+str(userName)+"_"+"User"
		
		try:
			new_issue = jira.create_issue(project={'key':str(pKey)}, summary=Summary, description=desc, issuetype={'name':'Bug'})
			print("Issue Id: %s" %(new_issue))
			jira.assign_issue(new_issue,'admin')
			# Logic for attaching files in the newly created Issue.
			if ptV is not None:
				fileWrite(ptV,'ptVideo.json')
				addAttachment(jira,new_issue,'ptVideo.json')
				deleteFile('ptVideo.json')
			if ptA is not None:
				fileWrite(ptA,'ptAudio.json')
				addAttachment(jira,new_issue,'ptAudio.json')
				deleteFile('ptAudio.json')
			if ptWhite is not None:
				fileWrite(ptWhite,'ptWhiteboard.json')
				addAttachment(jira,new_issue,'ptWhiteboard.json')
				deleteFile('ptWhiteboard.json')
			if ptLive is not None:
				fileWrite(ptLive,'ptLiveStream.json')
				addAttachment(jira,new_issue,'ptLiveStream.json')
				deleteFile('ptLiveStream.json')
			if ptScreen is not None:
				fileWrite(ptScreen,'ptScreen.json')
				addAttachment(jira,new_issue,'ptScreen.json')
				deleteFile('ptScreen.json')
			if ptVideoAsset is not None:
				fileWrite(ptVideoAsset,'ptVideoAssetStream.json')
				addAttachment(jira,new_issue,'ptVideoAssetStream.json')
				deleteFile('ptVideoAssetStream.json')
			if ptLocal is not None:
				fileWrite(ptLocal,'ptLocal.json')
				addAttachment(jira,new_issue,'ptLocal.json')
				deleteFile('ptLocal.json')
		except JIRAError as e:
			print(e)
			error = jiraErrorinfo(e.status_code)
			print(error)
	return True

def fileWrite(data,filename):
	try:
		with open(filename,'w') as file:
			file.write(data)
	except IOError as e:
		print(e)

def addAttachment(jira,issuename,filename):
	try:
		with open(filename,'rb') as file:
			jira.add_attachment(issue=issuename,attachment=file)
		print("%s file attached to %s issue" %(filename,issuename))
	except (JIRAError,IOError) as e:
		print(e)

def deleteFile(filename):
	if os.path.isfile(filename):
		# print("Found File!")
		os.remove(filename)
		# print("Succesfully Removed the %s file" %(filename))
	else:
		print("File Not Found!")

def main():
	hostname = '34.192.111.245'
	db_username = 'dbuser'
	db_password = 'dbuser123'
	print("Connecting To Vega Database.....")
	try:
		conn = pymysql.connect(hostname,db_username,db_password)
		print("Connection Sucessfull")
		q = "select value from vega.tblConfigure where searchKey = 'BUG_REPORT_LAST_READ_RECORD_ID'"
		cur = conn.cursor()
		cur.execute(q)
		ret = cur.fetchall()
		# print(ret)
		# checks whether the value returned is '0' or not
		if ret[0][0] is not '0':
			idWebRtc = ret[0][0] # if not '0' read the bug-reports after the last webrtc ID
		else:
			idWebRtc = 0 # if '0' read all the bug-reports repoted till now

		if idWebRtc is not 0:
			print(idWebRtc)
			df = queryExecution(conn,idWebRtc) # Program will insert all the bug reports after the webrtc id if there is.
		else:
			df = queryExecution(conn,False) # Program will insert all the bug reports which has been reported till now
		
		# if created dataframe is empty, means there is no records available.
		if df.empty: 
			print("No Records Available!")
		else:
			df.columns.values[17]='cpysessKey' # changing the name of the column
			# dropping the columns which I don't want.
			df.drop(df.columns[[16,17,19,20,21,22,23,27,28,29,31,32,33]], axis = 1,inplace=True)
			# print("Total Number of columns in Dataframe: %d" %(len(df.columns.values)))
			# print("Total Number of rows in Dataframe: %d" %(len(df)))
			insertDatabase(conn,(df.iloc[len(df)-1].idtblSessWebRtc)) # inserting the last record read webrtc ID
			
			# JIRA Authentication
			ret,jiraInfo = basicAuthentication()
			
			if ret == True:
				proList = projectDetails(jiraInfo)
				print("Project Details Is Shown Below:")
				proList.sort(key=lambda x:x.name)
				printProjectDetails(jiraInfo,proList)
				projectName = 'Support Admin'
				if len(proList) == 1:
					if(proList[0].name is not projectName):
						print("%s Not Present!" %(projectName))
					else:
						r=insertBugReport(jiraInfo,df,proList[0])
						if r == True:
							print("All Bugs Inserted!")
						else:
							print("Bugs Not Inserted!")
				else:
					index = -1
					index = binarySearch(projectName,proList) # checking whether the projectname ois present in the list of projects or not.
					if index is not (-1):
						r=insertBugReport(jiraInfo,df,proList[index])
						if r == True:
							print("All Bugs Inserted!")
						else:
							print("Bugs Not Inserted!")
					else:
						print("%s Not Present!" %(projectName))
			else:
				print(jira)

		# remove this part after final code written
		query = "update vega.tblConfigure set value = 0 where searchKey = 'BUG_REPORT_LAST_READ_RECORD_ID'"
		cur.execute(query)
		conn.commit()
	except pymysql.Error as e:
		print(e)
	finally:
		conn.close()

if __name__ == "__main__":
	main()
