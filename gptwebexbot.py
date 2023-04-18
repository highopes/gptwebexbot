from webexteamsbot import TeamsBot
from my_py.gpt_webex.credentials import *
import requests
import logging
import json
import re
import openai
import paramiko

requests.packages.urllib3.disable_warnings()

openai.api_key = OPENAI_KEY

# following is the prompt for ChatGPT
PROMPT_K8S01 = ('''I will enter a sentence, and you will do the linguistic analysis  '''
                '''and modify the JSON data: {"Language":"", "Target":"", "Name":"", "Type":""},  '''
                '''then return the modified JSON data to me.  '''
                '''First determine the language used in the sentence and let the value of Key "Language"  '''
                '''be the name of the language (type is English string). '''
                '''If you think I have mentioned a service or microservice or micro-service in my input,  '''
                '''then set the Value of the Key "Target" to the word "service", set the value of the Key "Name"  '''
                '''to the service name; '''
                ''' if you think I'm asking about the health  '''
                '''or quality of experience of the service or microservice or micro-service, then set the  '''
                '''value of the Key "Type" to "FSO". '''
                '''If you think this sentence is asking for the status of a specific Kubernetes cluster, then set  '''
                '''the value of the key "Target" to the name of that cluster, and set the value of the  '''
                '''key "Type" to "K8S".  If namespace is mentioned, then set the value of the key "Name" to  '''
                '''the name of the namespace.  '''
                '''If none of the above, then output this JSON  '''
                '''data directly without making any changes. Your MUST ONLY response the JSON data. You MUST NOT  '''
                '''add any extra characters. Now analyze the following sentence and output the JSON data: ''')

PROMPT_K8S02 = ('''Based on your knowledge of the Flow Telemetry information for the underlying network  '''
                '''provided by the Cisco Nexus Insights product, and you already know that this is traffic  '''
                '''information within the Kubernetes cluster, when there is an alert message (the alert is in  '''
                '''JSON format) as follows: {}   Please tell me what is the anomaly of this service flow, what is  '''
                '''the cause of the deterioration of the quality of service, and what are the possible  '''
                '''solutions.  '''
                '''Please start with language like this: After insight, we found network anomalies.  '''
                '''Please answer in {} language, and try to explain more''')

PROMPT_K8S03 = ('''You are now an application and I give you an administrative task below about the  '''
                '''Kubernetes system (k8s version is 1.21, CNI is Calico with IPIP=never and SNAT disabled),  '''
                '''you give the command line to complete that task directly and your answer must only  '''
                '''contain ONE command line in plain text that I can execute directly without any modification.  '''
                '''Do not use any formatting notation, just give the command line itself! '''
                '''I give the following task:  ''')

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


def configbyssh(host, cmd):
    '''
    SSHClient Testing
    '''
    try:
        # create sshClient obj
        ssh = paramiko.SSHClient()
        # trust remote host, allow access
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    except:
        print("There is an error with the SSHClient")
    try:
        # connect to remote host
        ssh.connect(host["host"],
                    host["port"],
                    host["user"],
                    host["pass"])
    except:
        print("Failed to connect to remote server")
    ''' 
    execute the commands 
    '''
    try:
        # note that every time we execute will be in new env
        stdin, stdout, stderr = ssh.exec_command(cmd)

        if stderr.readlines():
            print(stderr.readlines())

        result = stdout.read()
        result_str = result.decode('utf-8')

        return result_str

    except:
        print('Fail to execute command')

    # close ssh session
    ssh.close()


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
    added by Weihang
    """
    # ToDo:  use NDI API to get anomalies related to ip addresses, and return anomalies list

    return anomaly


def get_svc_address(svc):
    """
    added by Weihang
    """
    # ToDo:  use kubectl get pods -A -l app=svc -o jsonpath='{range .items[*]}{.status.podIP}{","}{end}' to get ip addesses

    return ip


def check_svc_network(svc):
    """
    added by Weihang
    """
    ipadd = []
    ipadd.extend(get_svc_address(svc))
    str = ""
    if ipadd:
        str = get_flow_anomalies(ipadd)

    return str


def ask_k8s(msg):
    """
    added by Weihang
    """
    # Analyze the prompt and return task JSON data
    prompt = PROMPT_K8S01 + msg.text
    task = json.loads(chat_withoutlog(prompt))
    print(task)
    language = task["Language"]

    # ask question based on task analysis
    if task["Type"] == "K8S":
        if task["Name"]:
            question = PROMPT_K8S03 + "In the namespace {}, ".format(task["Name"]) + msg.text
        else:
            question = PROMPT_K8S03 + msg.text
        print("question ---> ", question)
        k8s_cmd = chat_withoutlog(question)
        print(k8s_cmd)
        if "kubectl" in k8s_cmd or "calicoctl" in k8s_cmd:
            answer = configbyssh(SSH_HOST, k8s_cmd)
        else:
            answer = k8s_cmd

    else:
        anomalies = ""
        if task["Type"] == "FSO":
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
bot.add_command("/k8s",
                "Help improve your Kubernetes network (e.g. /k8s please list all pods' IP addresses of the movies microservice in the Namespace smm-demo in the Kubernetes cluster; /k8s 微服务movies的质量变差了, 网络出问题了吗; /k8s 帮我在Kubernetes集群创建一个名为test001的命名空间） ",
                ask_k8s)

bot.remove_command("/echo")

if __name__ == "__main__":
    # Run Bot
    logging.basicConfig(level=logging.NOTSET, filename='output.log', filemode='a',
                        format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info('loggin on here ')
    logging.NOTSET
    bot.run(host="0.0.0.0", port=8182)
