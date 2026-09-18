import hashlib, io, json, re, secrets
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import streamlit as st
from openai import OpenAI
from pypdf import PdfReader
from docx import Document

st.set_page_config(page_title='AI Resume & Application Assistant', page_icon='🤖', layout='wide')
st.markdown('''<style>
.main-title{font-size:2.4rem;font-weight:800;color:#17324d}.subtitle{color:#607080}.card{padding:1rem;border-radius:14px;border:1px solid rgba(128,128,128,.2);background:rgba(128,128,128,.05)}
.login-shell{max-width:1050px;margin:2rem auto;background:#fff;border-radius:24px;overflow:hidden;box-shadow:0 20px 60px rgba(23,50,77,.14);border:1px solid #e5e9ed}.login-form{padding:3.5rem 4rem 3rem}.login-form h1{font-size:2.8rem;line-height:1;margin:0;color:#15191d}.login-rule{width:38px;border:0;border-top:2px solid #202326;margin:1.5rem 0 3.5rem}.login-panel{min-height:580px;padding:3.5rem 3rem;background:linear-gradient(145deg,#17324d,#236b73);color:#fff;display:flex;flex-direction:column;justify-content:flex-end}.login-panel h2{font-size:2.7rem;margin:0 0 .5rem;letter-spacing:.02em}.login-panel p{font-size:1.05rem;margin:0;color:rgba(255,255,255,.85)}.login-muted{color:#93a2ad;font-size:.85rem}.login-button{background:#17191b;color:white;border-radius:999px;padding:.8rem 1rem;text-align:center;font-weight:700}.login-footer{text-align:center;color:#93a2ad;font-size:.85rem;margin-top:2.5rem}.login-footer b{color:#202326}
.dash-hero{padding:2rem;border-radius:22px;background:linear-gradient(120deg,#17324d,#236b73);color:white;margin:1rem 0 1.5rem}.dash-hero h1{font-size:2.2rem;margin:0 0 .4rem}.dash-hero p{font-size:1.05rem;margin:0;opacity:.86}.plan{min-height:310px;padding:1.4rem;border-radius:18px;border:1px solid #d9e1e8;background:#fff;box-shadow:0 8px 24px rgba(23,50,77,.07)}.plan.featured{border:2px solid #e7a83b;box-shadow:0 12px 30px rgba(231,168,59,.18)}.plan h3{margin:0;color:#17324d}.price{font-size:2rem;font-weight:800;color:#17324d;margin:.7rem 0}.plan ul{padding-left:1.1rem;line-height:1.9;color:#526270}.eyebrow{font-size:.76rem;letter-spacing:.08em;text-transform:uppercase;color:#b87516;font-weight:700}
</style>''', unsafe_allow_html=True)

if 'plan' not in st.session_state: st.session_state.plan='Free'
if 'logged_in' not in st.session_state: st.session_state.logged_in=False
if 'page' not in st.session_state: st.session_state.page='Dashboard'
if 'nav_page' not in st.session_state: st.session_state.nav_page='Dashboard'
if 'users' not in st.session_state: st.session_state.users={}
if 'auth_mode' not in st.session_state: st.session_state.auth_mode='login'
if 'oauth_state' not in st.session_state: st.session_state.oauth_state=secrets.token_urlsafe(24)

def key():
    try: return st.secrets.get('OPENAI_API_KEY','')
    except Exception: return ''

def secret_value(name):
    try: return st.secrets.get(name, '')
    except Exception: return ''

def password_hash(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def google_configured():
    return bool(secret_value('GOOGLE_CLIENT_ID') and secret_value('GOOGLE_CLIENT_SECRET'))

def google_login_url():
    redirect_uri=secret_value('GOOGLE_REDIRECT_URI') or 'http://localhost:8501/'
    query=urlencode({'client_id':secret_value('GOOGLE_CLIENT_ID'),'redirect_uri':redirect_uri,'response_type':'code','scope':'openid email profile','state':st.session_state.oauth_state,'access_type':'offline','prompt':'select_account'})
    return f'https://accounts.google.com/o/oauth2/v2/auth?{query}'

def complete_google_login():
    code=st.query_params.get('code')
    state=st.query_params.get('state')
    if not code or state != st.session_state.oauth_state or not google_configured(): return
    redirect_uri=secret_value('GOOGLE_REDIRECT_URI') or 'http://localhost:8501/'
    payload=urlencode({'code':code,'client_id':secret_value('GOOGLE_CLIENT_ID'),'client_secret':secret_value('GOOGLE_CLIENT_SECRET'),'redirect_uri':redirect_uri,'grant_type':'authorization_code'}).encode()
    try:
        token_data=json.loads(urlopen(Request('https://oauth2.googleapis.com/token',data=payload,headers={'Content-Type':'application/x-www-form-urlencoded'}),timeout=10).read())
        profile=json.loads(urlopen(Request('https://openidconnect.googleapis.com/v1/userinfo',headers={'Authorization':f"Bearer {token_data['access_token']}"}),timeout=10).read())
        st.session_state.logged_in=True
        st.session_state.user_email=profile.get('email','Google user')
        st.session_state.page='Dashboard'
        st.query_params.clear()
        st.rerun()
    except Exception as error:
        st.session_state.google_error=f'Google sign-in failed: {error}'

def close_login_page():
    st.session_state.page=st.session_state.nav_page

complete_google_login()

def ai(prompt, system='You are an expert resume and career assistant.'):
    if not key(): return ''
    r=OpenAI(api_key=key()).responses.create(model='gpt-5-mini', instructions=system, input=prompt)
    return r.output_text.strip()

def extract(f):
    if not f: return ''
    b=f.getvalue(); n=f.name.lower()
    if n.endswith('.pdf'):
        return '\n'.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(b)).pages).strip()
    if n.endswith('.docx'):
        return '\n'.join(p.text for p in Document(io.BytesIO(b)).paragraphs if p.text.strip()).strip()
    return b.decode('utf-8',errors='ignore')

def heuristic(resume,jd):
    r=resume.lower(); words=re.findall(r'[a-zA-Z][a-zA-Z0-9+#.-]{2,}',jd.lower())
    stop={'the','and','for','with','that','this','are','you','your','our','from','will','have','has','job','role','work','using','into','looking','candidate','experience','required','preferred','about'}
    keys=[]
    for w in words:
        if w not in stop and w not in keys: keys.append(w)
    matched=[w for w in keys if w in r]; missing=[w for w in keys if w not in r]
    return {'score':round(100*len(matched)/max(1,len(keys))),'matched':matched[:30],'missing':missing[:30]}

def jload(text):
    text=re.sub(r'^```json\s*','',text.strip(),flags=re.I); text=re.sub(r'\s*```$','',text)
    try:return json.loads(text)
    except:return None

def fallback_resume(p):
    return f"{p['name'].upper()}\n{p['contact']}\n\nSUMMARY\n{p['summary']}\n\nEDUCATION\n{p['education']}\n\nSKILLS\n{p['skills']}\n\nPROJECTS\n{p['projects']}\n\nEXPERIENCE\n{p['experience']}\n\nCERTIFICATIONS\n{p['certifications']}\n\nACHIEVEMENTS\n{p['achievements']}\n\nINTERESTS\n{p['interests']}"

if 'resume' not in st.session_state: st.session_state.resume=''
if 'generated' not in st.session_state: st.session_state.generated=''
if 'analysis' not in st.session_state: st.session_state.analysis=None
if 'cover' not in st.session_state: st.session_state.cover=''

with st.sidebar:
    st.markdown('## 🤖 AI Resume Assistant')
    if st.button('Login', use_container_width=True):
        st.session_state.page='Login'
        st.rerun()
    nav_page=st.radio('Navigation',['Dashboard','Resume Maker','ATS Analyzer','Job Matcher','Cover Letter','Application Assistant','Interview Prep'],key='nav_page',on_change=close_login_page)
    page='Login' if st.session_state.page=='Login' else nav_page
    st.divider()
    if st.session_state.logged_in:
        st.caption(f"Signed in as {st.session_state.get('user_email','user')}")
        if st.button('Sign out', use_container_width=True):
            st.session_state.logged_in=False
            st.session_state.page='Login'
            st.rerun()
    else:
        st.caption('Guest session')
    if key():
        st.success('AI API configured')
    else:
        st.warning('AI API not configured — fallback mode')

st.markdown('<div class="main-title">AI Resume & Application Assistant</div>',unsafe_allow_html=True)
st.markdown('<div class="subtitle">Create • Analyze • Match • Apply • Prepare</div>',unsafe_allow_html=True)

if page=='Login':
    if st.session_state.get('google_error'):
        st.error(st.session_state.pop('google_error'))
    left, right=st.columns(2, gap='large')
    with left:
        title='Create account' if st.session_state.auth_mode=='signup' else 'Login'
        st.markdown(f'<div class="login-form"><h1>{title}</h1><hr class="login-rule"></div>', unsafe_allow_html=True)
        with st.form('auth'):
            email=st.text_input('Email Address / Mobile Number', placeholder='you@example.com')
            password=st.text_input('Password', type='password')
            confirm=st.text_input('Confirm Password', type='password') if st.session_state.auth_mode=='signup' else ''
            submitted=st.form_submit_button('SIGN UP' if st.session_state.auth_mode=='signup' else 'LOGIN', use_container_width=True)
        if st.session_state.auth_mode=='signup':
            if st.button('Back to Login', use_container_width=True):
                st.session_state.auth_mode='login'
                st.rerun()
        elif st.button("You don't have an account? SIGN UP", use_container_width=True):
            st.session_state.auth_mode='signup'
            st.rerun()
        if google_configured():
            st.link_button('Continue with Google', google_login_url(), use_container_width=True)
        else:
            if st.button('Continue with Google', use_container_width=True):
                st.warning('Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .streamlit/secrets.toml to enable Google sign-in.')
    with right:
        st.markdown('<div class="login-panel"><h2>WELCOME</h2><p>Let\'s get started</p></div>', unsafe_allow_html=True)
        st.markdown('<div style="padding-top:1rem"><b>Choose your workspace plan</b><br><span class="login-muted">You can change this later from the dashboard.</span></div>', unsafe_allow_html=True)
        selected_plan=st.selectbox('Plan', ['Free','Pro','Premium'], label_visibility='collapsed')
    if submitted:
        normalized_email=email.strip().lower()
        if not normalized_email or not password:
            st.warning('Enter an email address and password to continue.')
        elif st.session_state.auth_mode=='signup':
            if password != confirm:
                st.error('Passwords do not match.')
            elif normalized_email in st.session_state.users:
                st.error('An account with this email already exists. Please log in.')
            else:
                st.session_state.users[normalized_email]=password_hash(password)
                st.session_state.logged_in=True
                st.session_state.user_email=normalized_email
                st.session_state.plan=selected_plan
                st.session_state.auth_mode='login'
                st.session_state.page='Dashboard'
                st.rerun()
        elif st.session_state.users.get(normalized_email) != password_hash(password):
            st.error('Incorrect email or password. Sign up first if you are new here.')
        else:
            st.session_state.logged_in=True
            st.session_state.user_email=normalized_email
            st.session_state.plan=selected_plan
            st.session_state.page='Dashboard'
            st.rerun()

elif page=='Dashboard':
    st.markdown(f'''<div class="dash-hero"><div class="eyebrow">Your career workspace</div><h1>Move from application to offer.</h1><p>Build a stronger resume, tailor every application, and prepare with confidence.</p></div>''',unsafe_allow_html=True)
    a,b,c,d=st.columns(4); a.metric('Resume','Ready' if st.session_state.resume else 'Not uploaded'); b.metric('ATS Score',f"{st.session_state.analysis['score']}%" if st.session_state.analysis else '—'); c.metric('AI Mode','Online' if key() else 'Fallback'); d.metric('Plan',st.session_state.plan)
    st.subheader('🚀 Your toolkit')
    for x in [('📄 Resume Maker','Build an ATS-friendly resume.'),('🔍 ATS Analyzer','Compare a resume with a job description.'),('🎯 Job Matcher','Estimate job fit and missing skills.'),('✉️ Application Assistant','Generate cover letters, emails and interview answers.')]: st.markdown(f'<div class="card"><b>{x[0]}</b><br>{x[1]}</div>',unsafe_allow_html=True)

    st.subheader('Choose your plan')
    st.caption('Start free, upgrade when you need more applications and deeper AI support.')
    plans=[('Free','$0','For getting started',['1 resume workspace','3 ATS analyses / month','Basic job matching']),('Pro','$12 / month','For an active job search',['Unlimited resume versions','25 ATS analyses / month','Cover letters and application packs']),('Premium','$24 / month','For serious career momentum',['Unlimited AI tools','Advanced interview preparation','Priority application workflows'])]
    columns=st.columns(3)
    for column,(name,price,description,features) in zip(columns,plans):
        featured=name=='Pro'
        badge='<div class="eyebrow">Most popular</div>' if featured else ''
        items=''.join(f'<li>{feature}</li>' for feature in features)
        with column:
            st.markdown(f'<div class="plan {"featured" if featured else ""}">{badge}<h3>{name}</h3><div class="price">{price}</div><p>{description}</p><ul>{items}</ul></div>',unsafe_allow_html=True)
            if st.button('Current plan' if st.session_state.plan==name else f'Choose {name}',key=f'plan_{name.lower()}',use_container_width=True,disabled=st.session_state.plan==name):
                st.session_state.plan=name
                st.rerun()
elif page=='Resume Maker':
    st.subheader('📄 AI Resume Maker')
    with st.form('resume'):
        p={}
        p['name']=st.text_input('Full name','Sai Rudhrateja Reddy CH'); p['contact']=st.text_input('Contact','sai.reddy@example.com | +91 98765 43210 | Tamil Nadu, India'); p['summary']=st.text_area('Career summary'); p['education']=st.text_area('Education','B.Tech – Computer Science Engineering (AI & ML), Kalasalingam University | 2024–2028'); p['skills']=st.text_area('Technical skills','Python, JavaScript, C++, React.js, Node.js, Machine Learning, SQL, Git'); p['projects']=st.text_area('Projects',height=130); p['experience']=st.text_area('Experience / internships',height=90); p['certifications']=st.text_area('Certifications',height=70); p['achievements']=st.text_area('Achievements',height=70); p['interests']=st.text_area('Areas of interest','Artificial Intelligence, Machine Learning, Full-Stack Development, IoT'); go=st.form_submit_button('✨ Generate Resume',use_container_width=True)
    if go:
        prompt=f'''Create a concise ATS-friendly fresher resume from this data. Do not invent facts. Use sections SUMMARY, EDUCATION, SKILLS, PROJECTS, EXPERIENCE, CERTIFICATIONS, ACHIEVEMENTS and INTERESTS where applicable.\n{json.dumps(p,indent=2)}'''
        with st.spinner('Creating resume...'): st.session_state.generated=ai(prompt) or fallback_resume(p)
    if st.session_state.generated:
        st.text_area('Generated Resume',st.session_state.generated,height=650); st.download_button('⬇️ Download TXT',st.session_state.generated,'ai_resume.txt','text/plain',use_container_width=True)

elif page=='ATS Analyzer':
    st.subheader('🔍 ATS Resume Analyzer')
    f=st.file_uploader('Upload Resume',type=['pdf','docx','txt']); jd=st.text_area('Paste Job Description',height=300)
    if f:
        try: st.session_state.resume=extract(f); st.success(f"Loaded {len(st.session_state.resume.split())} words")
        except Exception as e: st.error(str(e))
    if st.button('🔎 Analyze ATS Score',use_container_width=True):
        if not st.session_state.resume or not jd: st.warning('Upload a resume and paste a job description first.')
        else:
            base=heuristic(st.session_state.resume,jd)
            prompt=f'''Analyze resume vs job description. Return JSON only: {{"score":0,"strengths":[],"missing_keywords":[],"improvements":[],"summary":""}}. Do not invent facts. RESUME:\n{st.session_state.resume[:18000]}\nJOB:\n{jd[:18000]}'''
            with st.spinner('Analyzing...'): out=ai(prompt)
            data=jload(out) if out else None
            st.session_state.analysis=data or {'score':base['score'],'strengths':base['matched'],'missing_keywords':base['missing'],'improvements':['Add truthful job-specific keywords.','Use measurable project outcomes.','Keep formatting ATS-friendly.'],'summary':'Basic keyword analysis used because AI API is not configured.'}
    if st.session_state.analysis:
        x=st.session_state.analysis; st.metric('ATS Match Score',f"{x['score']} / 100"); st.progress(max(0,min(100,int(x['score'])))/100); st.info(x.get('summary','')); st.markdown('**Strengths:** '+', '.join(x.get('strengths',[]))); st.markdown('**Missing keywords:** '+', '.join(x.get('missing_keywords',[]))); st.markdown('**Improvements:**'); [st.write('• '+z) for z in x.get('improvements',[])]

elif page=='Job Matcher':
    st.subheader('🎯 Job Matcher'); resume=st.text_area('Resume',st.session_state.resume,height=250); job=st.text_area('Job description',height=250)
    if st.button('🎯 Calculate Job Match',use_container_width=True):
        base=heuristic(resume,job); out=ai(f'''Compare resume and job. Return JSON only: {{"match_score":0,"matched_skills":[],"missing_skills":[],"recommendation":""}}. Do not invent facts.\nRESUME:{resume[:15000]}\nJOB:{job[:15000]}'''); data=jload(out) if out else None; data=data or {'match_score':base['score'],'matched_skills':base['matched'],'missing_skills':base['missing'],'recommendation':'Improve the resume using truthful, relevant skills and evidence.'}; st.metric('Job Match',f"{data['match_score']}%"); st.progress(max(0,min(100,int(data['match_score'])))/100); st.write('**Matched:**',', '.join(data.get('matched_skills',[]))); st.write('**Missing:**',', '.join(data.get('missing_skills',[]))); st.info(data.get('recommendation',''))

elif page=='Cover Letter':
    st.subheader('✉️ Cover Letter Generator'); resume=st.text_area('Resume/Profile',st.session_state.resume,height=220); company=st.text_input('Company','Example Technologies'); role=st.text_input('Job title','Machine Learning Intern'); job=st.text_area('Job description',height=220)
    if st.button('✨ Generate Cover Letter',use_container_width=True):
        out=ai(f'''Write a concise professional cover letter for {role} at {company}. Use only facts in the resume and tailor to the job.\nRESUME:{resume[:15000]}\nJOB:{job[:15000]}'''); st.session_state.cover=out or f'''Dear Hiring Manager,\n\nI am writing to apply for the {role} position at {company}. My academic background and project experience align with the role, and I am eager to contribute while continuing to develop my skills.\n\nThank you for considering my application.\n\nSincerely,\nCandidate'''
    if st.session_state.cover: st.text_area('Cover Letter',st.session_state.cover,height=450); st.download_button('⬇️ Download',st.session_state.cover,'cover_letter.txt','text/plain',use_container_width=True)

elif page=='Application Assistant':
    st.subheader('📨 Application Assistant'); resume=st.text_area('Resume/Profile',st.session_state.resume,height=180); company=st.text_input('Company','Example Technologies'); role=st.text_input('Role','Software Engineer Intern'); job=st.text_area('Job description',height=200)
    if st.button('🚀 Generate Application Pack',use_container_width=True):
        out=ai(f'''Create an application pack for {role} at {company}. Return JSON only: {{"application_email_subject":"","application_email":"","linkedin_message":"","why_me":"","tell_me_about_yourself":""}}. Use only truthful resume facts.\nRESUME:{resume[:15000]}\nJOB:{job[:15000]}'''); data=jload(out) if out else None; data=data or {'application_email_subject':f'Application for {role}','application_email':f'Dear Hiring Manager,\n\nI am interested in the {role} opportunity at {company}. Please find my resume attached for your consideration.\n\nRegards,\nCandidate','linkedin_message':f'Hello, I am interested in the {role} opportunity at {company}. I would appreciate the opportunity to connect.','why_me':'My academic projects and technical skills provide a strong foundation for the role.','tell_me_about_yourself':'I am a motivated technology student with experience building academic projects in software and AI/ML.'};
        for k,v in data.items(): st.markdown('### '+k.replace('_',' ').title()); st.text_area(k,v,height=180 if k=='application_email' else 100)

else:
    st.subheader('🎤 AI Interview Preparation'); role=st.text_input('Target role','Machine Learning Intern'); job=st.text_area('Job description',height=220); resume=st.text_area('Resume',st.session_state.resume,height=180)
    if st.button('🎤 Generate Interview Kit',use_container_width=True):
        out=ai(f'''Create an interview kit. Return JSON only: {{"questions":[{{"question":"","why_asked":"","answer_framework":""}}],"technical_topics":[],"tips":[]}}. Do not claim skills not in resume.\nROLE:{role}\nJOB:{job[:12000]}\nRESUME:{resume[:12000]}'''); data=jload(out) if out else None; data=data or {'questions':[{'question':'Tell me about yourself.','why_asked':'Tests communication.','answer_framework':'Present → skills → projects → why role.'},{'question':'Explain one project.','why_asked':'Tests technical ownership.','answer_framework':'Problem → approach → technology → result.'}], 'technical_topics':['Programming','Data structures','Machine learning basics','SQL'],'tips':['Use specific examples.','Do not exaggerate experience.']};
        for q in data['questions']:
            with st.expander(q['question']): st.write('**Why asked:**',q['why_asked']); st.write('**Framework:**',q['answer_framework'])
        st.markdown('### Technical topics'); st.write(', '.join(data['technical_topics'])); st.markdown('### Tips'); [st.write('• '+t) for t in data['tips']]

st.divider(); st.caption('Review AI-generated content before submitting. Never add skills or experience you do not actually have.')
