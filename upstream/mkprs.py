import re, json, os, subprocess
T=os.environ['GT']; API='https://git.konn3kt.com/api/v1/repos/IQ.Lvbs/IQ.Pilot/pulls'
md=open('PR_DESCRIPTIONS.md').read()
secs=re.split(r'\n## (\d+)\. ', md)[1:]
branches=['fix/personality-button-blocking-put','hyundai/tucson-4th-gen-fw-cw020','hyundai/tucson-canfd-startup-arming','hyundai/tucson-main-button-keeps-long','cruise/set-adopts-current-speed','hyundai/tucson-canfd-launch-smoothing','hyundai/tucson-lateral-tune','long/stop-and-cruise-tuning']
links={}
for i in range(0,len(secs),2):
    n=int(secs[i]); body=secs[i+1].split('\n---')[0]
    lines=body.strip().split('\n'); assert lines[0].strip()==branches[n-1], lines[0]
    m=re.search(r'\*\*(.+?)\*\*', body); title=m.group(1)
    rest=body[m.end():].strip().replace('`<PR_3_LINK>`', links.get(3,'')).replace('<PR_3_LINK>', links.get(3,''))
    rest += "\n\nAnalysis, drive data and offline replays: https://github.com/Amacfa/tucson-iqpilot-tuning"
    payload={'base':'release-candidate','head':'rozal:'+branches[n-1],'title':title,'body':rest}
    out=subprocess.run(["curl","-s","-m","60","-A","curl/8","-H","Authorization: token "+T,"-H","Content-Type: application/json",API,"-d",json.dumps(payload)],capture_output=True,text=True).stdout
    d=json.loads(out) if out.strip().startswith("{") else {"message":out[:200]}
    if "html_url" in d: links[n]=d["html_url"]; print(n,d["number"],d["html_url"],"|",title)
    else: print(n,"ERR",d.get("message"))
