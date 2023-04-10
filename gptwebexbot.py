from webexteamsbot import TeamsBot
from my_py.gpt_webex.credentials import *
import requests
import logging
import json
import re
import openai

requests.packages.urllib3.disable_warnings()

openai.api_key = OPENAI_KEY

# following is the prompt for ChatGPT
PROMPT_K8S01 = ('''I will enter a sentence, and you will do the linguistic analysis  '''
                '''and modify the JSON data: {"Language":"", "Target":"", "Name":"", "Type":""},  '''
                '''then return the modified data to me.  '''
                '''First determine the language used in the sentence and let the value of Key "Language"  '''
                '''be the name of the language (type is English string). '''
                '''If you think I have mentioned a service or microservice or micro-service in my input,  '''
                '''then change the Value of the item with Key "Target" to "service", and Key "Name " to the name  '''
                '''of the service or microservice or micro-service; if you think I'm asking about the health  '''
                '''or quality of experience of the service or microservice or micro-service, then change the  '''
                '''Value of the item with the Key "Type" to "FSO ". If none of the above, then output this JSON  '''
                '''data directly without making any changes. Your answer only needs to contain JSON data, no other  '''
                '''extra characters. Now analyze the following sentence and output the JSON data: ''')

PROMPT_K8S02 = ('''Based on your knowledge of the Flow Telemetry information for the underlying network  '''
                '''provided by the Cisco Nexus Insights product, and you already know that this is traffic  '''
                '''information within the Kubernetes cluster, when there is an alert message (the alert is in  '''
                '''JSON format) as follows: {}   Please tell me what is the anomaly of this service flow, what is  '''
                '''the cause of the deterioration of the quality of service, and what are the possible  '''
                '''solutions.  '''
                '''Please start with language like this: After insight, we found network anomalies.  '''
                '''Please answer in {} language, and try to explain more''')

base_url = "https://api.thousandeyes.com/v6/"

# chatGPT url and Header
# chatGPT_url = "https://api.openai.com/v1/completions"
# url = "https://api.openai.com/v1/engines/text-davinci-003/jobs"
chatGPT_headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer ' + openai.api_key
}

bot = TeamsBot(
    TEAMS_BOT_APP_NAME,
    teams_bot_token=WEBEX_TEAMS_ACCESS_TOKEN,
    teams_bot_url=TEAMS_BOT_URL,
    teams_bot_email=TEAMS_BOT_EMAIL,
    debug=True,
    webhook_resource_event=[
        {"resource": "messages", "event": "created"},
    ],
)

TE_headers = {
    "Authorization": "Bearer " + TETOKEN,
    "Accept": "application/json",
    "Content-Type": "application/json"
}


# A simple command that returns a basic string that will be sent as a reply
def list_agents(incoming_msg):
    message = "TE said:\nHere is your list of agents:<br /><br />"
    res = requests.get(url=base_url + "endpoint-agents", headers=TE_headers)
    data = json.loads(res.text)
    for agent in data['endpointAgents']:
        message = message + (f"Agent Name: {agent['agentName']} - Type: {agent['agentType']}<br />")

    return message


def list_tests(incoming_msg):
    message = "TE said:\nHere is your list of tests:<br /><br />"
    res = requests.get(url=base_url + "tests", headers=TE_headers)
    data = json.loads(res.text)
    for test in data['test']:
        message = message + (f"Test ID: {test['testId']} - Type: {test['type']} - Test Name: {test['testName']}<br />")

    return message


def test_details(incoming_msg):
    message = incoming_msg.text
    test_id = str(re.sub('[^0-9]', '', message))
    res = requests.get(url=base_url + "tests/" + test_id, headers=TE_headers)
    data = json.loads(res.text)
    print(data)
    for test in data['test']:
        message = f"""Test ID: {test['testId']}
                    Type: {test['type']}
                    Test Name: {test['testName']}
                    Interval: {test['interval']}
                    Path Traces: {test['numPathTraces']}"""

    return message


# Active alarm
def list_alerts(incoming_msg):
    message = "TE Said:\nHere is your list of active alert:<br /><br />"
    res = requests.get(url=base_url + "alerts", headers=TE_headers)
    data = json.loads(res.text)
    print(data)
    for test in data['alert']:
        message = message + (f"Type: {test['active']} <br />")

    return message


# chatGPT
def chat_withoutlog(prompt, model="gpt-3.5-turbo", max_tokens=800):
    """
    add by Weihang
    """
    messages = [{"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}]

    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        n=1,
        stop=None,
        temperature=0.5,
    )

    return response.choices[0].message['content']


def chatGPT_send_message(message_log):
    # Use OpenAI's ChatCompletion API to get the chatbot's response
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",  # The name of the OpenAI chatbot model to use
        # model="gpt-4",  # The name of the OpenAI chatbot model to use
        messages=message_log,  # The conversation history up to this point, as a list of dictionaries
        max_tokens=3800,  # The maximum number of tokens (words or subwords) in the generated response
        stop=None,  # The stopping sequence for the generated response, if any (not used here)
        temperature=0.7,  # The "creativity" of the generated response (higher temperature = more creative)
    )

    # Find the first response from the chatbot that has text in it (some responses may not have text)
    for choice in response.choices:
        if "text" in choice:
            return choice.text

    # If no response with text is found, return the first response's content (which may be empty)
    return response.choices[0].message.content


def chatGPT_main(questions):
    # Initialize the conversation history with a message from the chatbot
    message_log = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Set a flag to keep track of whether this is the first request in the conversation
    user_input = questions
    message_log.append({"role": "user", "content": user_input})

    # Add a message from the chatbot to the conversation history
    message_log.append({"role": "assistant", "content": "You are a helpful assistant."})

    # Send the conversation history to the chatbot and get its response
    response = chatGPT_send_message(message_log)

    # Add the chatbot's response to the conversation history and print it to the console
    message_log.append({"role": "assistant", "content": response})
    print(f"AI assistant: {response}")
    response2 = response
    return response2


def ask_ChatGPT(questions):
    ask_questions = questions.text
    message = chatGPT_main(ask_questions)

    return message


# vManage Alarm
# vManage API endpoint for fetching alarms
def vManage_alarms(incoming_msg):
    message = "SDWAN Said:\nSDWAN Vmanage is under instruction,will update soon <br /><br />"

    return message


# SecureX API endpoint for fetching alarms
def securex_alarms(incoming_msg):
    message = "SecureX Said:\n SecureX Incident getting is under instruction, will update soon <br /><br />"

    return message


def for_help(incoming_msg):
    message = "Please contact xueatian@cisco.com for further discussion. Do not contact hangwe@cisco.com :)"

    return message


def get_token():
    auth_url = f"https://{dnac_ip}/dna/system/api/v1/auth/token"
    token = requests.post(
        auth_url, auth=(username, password),
        headers={"content-type": "application/json"},
        verify=False, )

    data = token.json()
    print(data)
    return data["Token"]


def get_issue_list_from_dnac(incoming_msg):
    message = "DNAC on Devnet Sanbox Said:\nHere is your list of active Issues:<br /><br />"
    token = get_token()
    # url=f"https://{dnac_ip}/dna/intent/api/v1/network-device"
    url = f"https://{dnac_ip}/dna/intent/api/v1/issues"

    response = requests.get(url, headers={"X-Auth-Token": token, "Content-type": "application/json"},
                            verify=False
                            )
    a = 1
    issue_all = {}
    for items in response.json()['response']:
        # print(items)
        items_name = items['name']
        issue_all[a] = items_name
        print(str(a) + ':' + items_name)
        message = message + (str(a) + "  :"f"Issue Name: {items_name} <br />")
        a += 1
    print(message)
    return message


# Ask the reason for Issue on ChatGPT
def ask_reason(number):
    token = get_token()
    # url=f"https://{dnac_ip}/dna/intent/api/v1/network-device"
    url = f"https://{dnac_ip}/dna/intent/api/v1/issues"

    response = requests.get(url, headers={"X-Auth-Token": token, "Content-type": "application/json"},
                            verify=False
                            )
    a = 1
    issue_all = {}

    for items in response.json()['response']:
        # print(items)
        items_name = items['name']
        issue_all[a] = items_name
        # print(str(a)+':'+items_name)
        a += 1

    print(issue_all)
    print(number)
    print(type(number))
    match = re.search(r'/ask-reason\s+(\S+)', number)

    # 输出匹配结果

    print(match.group(1))
    questions = issue_all[int(match.group(1))]
    print(questions)
    # Initialize the conversation history with a message from the chatbot
    message_log = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Set a flag to keep track of whether this is the first request in the conversation
    main_questions = "what is the meaning and main reason for"
    main_questions2 = "do not need the guide to fix it "
    user_input = main_questions + questions + main_questions2
    message_log.append({"role": "user", "content": user_input})

    # Add a message from the chatbot to the conversation history
    message_log.append({"role": "assistant", "content": "You are a helpful assistant."})

    # Send the conversation history to the chatbot and get its response
    response = chatGPT_send_message(message_log)

    # Add the chatbot's response to the conversation history and print it to the console
    message_log.append({"role": "assistant", "content": response})
    print(f"AI assistant: {response}")
    response2 = "AI said:\n" + response
    return response2


def ask_guide(number2):
    token = get_token()
    # url=f"https://{dnac_ip}/dna/intent/api/v1/network-device"
    url = f"https://{dnac_ip}/dna/intent/api/v1/issues"

    response = requests.get(url, headers={"X-Auth-Token": token, "Content-type": "application/json"},
                            verify=False
                            )
    a = 1
    issue_all = {}

    for items in response.json()['response']:
        # print(items)
        items_name = items['name']
        issue_all[a] = items_name
        # print(str(a)+':'+items_name)
        a += 1

    print(issue_all)
    print(number2)
    print(type(number2))
    match = re.search(r'/ask-guide\s+(\S+)', number2)

    # 输出匹配结果

    print(match.group(1))
    questions = issue_all[int(match.group(1))]
    print(questions)
    # Initialize the conversation history with a message from the chatbot
    message_log = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Set a flag to keep track of whether this is the first request in the conversation
    # main_questions = "please guide me how to fix this issue\" "
    main_questions = "请指导我如何处理这个告警\" "
    main_questions2 = "\"including the command line on device , and summary all the command line together finally "
    user_input = main_questions + questions + main_questions2
    print(user_input)
    message_log.append({"role": "user", "content": user_input})

    # Add a message from the chatbot to the conversation history
    message_log.append({"role": "assistant", "content": "You are a helpful assistant."})

    # Send the conversation history to the chatbot and get its response
    response = chatGPT_send_message(message_log)

    # Add the chatbot's response to the conversation history and print it to the console
    message_log.append({"role": "assistant", "content": response})
    print(f"AI assistant: {response}")
    response3 = "AI said:\n" + response
    return response3


def ask_guide_chinese(number2):
    token = get_token()
    # url=f"https://{dnac_ip}/dna/intent/api/v1/network-device"
    url = f"https://{dnac_ip}/dna/intent/api/v1/issues"

    response = requests.get(url, headers={"X-Auth-Token": token, "Content-type": "application/json"},
                            verify=False
                            )
    a = 1
    issue_all = {}

    for items in response.json()['response']:
        # print(items)
        items_name = items['name']
        issue_all[a] = items_name
        # print(str(a)+':'+items_name)
        a += 1

    print(issue_all)
    print(number2)
    print(type(number2))
    match = re.search(r'/ask-chinese-guide\s+(\S+)', number2)

    # 输出匹配结果

    print(match.group(1))
    questions = issue_all[int(match.group(1))]
    print(questions)
    # Initialize the conversation history with a message from the chatbot
    message_log = [
        {"role": "system", "content": "You are a helpful assistant."}
    ]

    # Set a flag to keep track of whether this is the first request in the conversation
    main_questions = "please guide me how to fix this issue\" "
    main_questions2 = "\" including the command line on device ,summary all the command line together finally,and describe that in Chinese only "
    user_input = main_questions + questions + main_questions2
    print(user_input)
    message_log.append({"role": "user", "content": user_input})

    # Add a message from the chatbot to the conversation history
    message_log.append({"role": "assistant", "content": "You are a helpful assistant."})

    # Send the conversation history to the chatbot and get its response
    response = chatGPT_send_message(message_log)

    # Add the chatbot's response to the conversation history and print it to the console
    message_log.append({"role": "assistant", "content": response})
    print(f"AI assistant: {response}")
    response3 = "AI said:\n" + response
    return response3


def ask_ChatGPT_reason(questions_number):
    ask_number = questions_number.text
    message = ask_reason(ask_number)

    return message


def ask_ChatGPT_guide(questions_number):
    ask_number = questions_number.text
    message = ask_guide(ask_number)

    return message


def ask_ChatGPT_guide_chinese(questions_number):
    ask_number = questions_number.text
    message = ask_guide_chinese(ask_number)

    return message


def get_flow_anomalies(ip):
    """
    add by Weihang
    """
    # ToDo:  use NDI API to get anomalies related to ip addresses, and return anomalies list
    anomaly = '''{
        "anomalyId": "FLOc8b14c3d5537623c608197f2b66be171b96decfb",
        "category": "flows",
        "startTs": "2023-03-31T13:03:30.731Z",
        "endTs": "2023-03-31T13:03:30.731Z",
        "activeTs": "2023-03-31T13:03:30.731Z",
        "anomalyScore": 61,
        "fabricName": "pek-aci",
        "entityName": "172.31.66.70,38977,10.124.4.61,53,UDP,CMP_VRF_VMM,CMP_VRF_VMM",
        "resourceType": "flow",
        "resourceName": "drop",
        "anomalyStr": "For flow from 172.31.66.70 port 38977 to 10.124.4.61 port 53, packet drop is detected due to forward drop, ",
        "anomalyReason": "for flow from 172.31.66.70 port 38977 to 10.124.4.61 port 53, packet drop is detected due to forward drop, ",
        "recommendation": false,
        "impact": true,
        "vendor": "CISCO_ACI",
        "severity": "major",
        "anomalyType": "drop",
        "acknowledged": false,
        "ackTs": null,
        "cleared": true,
        "streamingAnomaly": false,
        "clearTs": "2023-03-31T13:28:52.684Z",
        "masterClearTs": "2023-03-31T13:28:40.000Z",
        "expired": false,
        "alertType": "anomaly",
        "title": "",
        "targetIndex": "<cisco_nir-anomalydb-2023.03.31>",
        "customData": {},
        "epochStartTs": 1680267810731,
        "epochEndTs": 1680267810731,
        "epochActiveTs": 1680267810731,
        "mnemonicTitle": "FLOW_DROP",
        "mnemonicNum": 100103,
        "mnemonicDescription": "Packet drop detected due to forward drop",
        "entityNameList": [
            {
                "objectType": "leaf",
                "objectValue": [
                    "pod1_leaf102"
                ]
            }
        ],
        "offline": false,
        "verificationStatus": "NEW",
        "assignee": "",
        "tags": [],
        "comment": "",
        "manualAck": null,
        "autoAck": false,
        "hashKey": 2018151606363828,
        "checkCodes": [],
        "multiFabricAlert": false,
        "nodeNames": [
            "pod1_leaf102"
        ],
        "srcIp": "172.31.66.70",
        "srcPort": 38977,
        "dstIp": "10.124.4.61",
        "dstPort": 53,
        "protocolName": "UDP",
        "ingressVrf": "CMP_VRF_VMM",
        "egressVrf": "CMP_VRF_VMM"
    }'''

    return anomaly


def get_svc_address(svc):
    """
    add by Weihang
    """
    # ToDo:  use kubectl get pods -A -l app=svc -o jsonpath='{range .items[*]}{.status.podIP}{","}{end}' to get ip addesses
    ip = ["10.124.4.61"]

    return ip


def check_svc_network(svc):
    """
    add by Weihang
    """
    ipadd = []
    ipadd.extend(get_svc_address(svc))
    str = ""
    if ipadd:
        str = get_flow_anomalies(ipadd)

    return str


def ask_k8s(msg):
    """
    add by Weihang
    """
    prompt = PROMPT_K8S01 + msg.text

    task = json.loads(chat_withoutlog(prompt))
    print(task)
    language = task["Language"]
    anomalies = ""
    if "service" in task["Target"] and task["Type"] == "FSO":
        anomalies = check_svc_network(task["Name"])

    print("anomalies ---> ", anomalies)
    if anomalies:
        question = PROMPT_K8S02.format(anomalies, language)
        print("question ---> ", question)
        answer = chat_withoutlog(question)
    else:
        question = ('''Please express the following in {}:  '''
                    '''It appears that there is nothing wrong with your underlying network and  '''
                    '''the quality of service is likely to be a failure at the host, OS level  '''
                    '''or application level.  ''').format(language)
        print("question ---> ", question)
        answer = chat_withoutlog(question)

    return answer


# Add new commands to the box.
bot.add_command("/SDWAN-listalarms", "This will list the active alarms from SDWAN Vmanage", vManage_alarms)
bot.add_command("/gethelp", "please contact with xueatian@cisco.com. Do not contact hangwe@cisco.com :)", for_help)
bot.add_command("/te-listagents", "This will list the endpoint agents", list_agents)
bot.add_command("/te-listtests", "This will list the tests", list_tests)
bot.add_command("/te-testdetails",
                "This will provde more information about a test with the given Test ID (e.g. /testdetails 12345)",
                test_details)
bot.add_command("/te-listalerts", "This will list the active alerts", list_alerts)
bot.add_command("/askai", "ask questions to chatGPT, (e.q. /askai how beautiful is the life )", ask_ChatGPT)
bot.add_command("/dnac-listissues", "This will list the active issues from DNAC", get_issue_list_from_dnac)
bot.add_command("/ask-reason",
                "ask the detail description on the DNAC issue with chatGPT,input the issue number (e.q. /ask-reason  1 )",
                ask_ChatGPT_reason)
bot.add_command("/ask-guide",
                "ask the guide on how to fix the issues on DNAC with chatGPT,input the issue number (e.q. /ask-guide  1 )",
                ask_ChatGPT_guide)
bot.add_command("/ask-chinese-guide",
                "让chatGPT用中文描述这个故障的处理建议,输入的格式为/ask-chinese-guide + 故障编号 (e.q. /ask-chinese-guide  1 )",
                ask_ChatGPT_guide_chinese)
bot.add_command("/secure-listincidents", "This will list the active security incidents from SecureX platform ",
                securex_alarms)
bot.add_command("/k8s", "Help improve your Kubernetes network (e.g. /k8s 微服务movies的质量变差了, 网络出问题了吗) ",
                ask_k8s)

bot.remove_command("/echo")

if __name__ == "__main__":
    # Run Bot
    logging.basicConfig(level=logging.NOTSET, filename='output.log', filemode='a',
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info('loggin on here ')
    logging.NOTSET
    bot.run(host="0.0.0.0", port=8182)
