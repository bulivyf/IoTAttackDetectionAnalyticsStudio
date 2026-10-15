"""Explicit user-triggered media calls. Generated imagery/video are illustration, never evidence."""
import base64

def client(key):
    from openai import OpenAI
    return OpenAI(api_key=key,timeout=180,max_retries=0)

def image(key,prompt,model):
    response=client(key).images.generate(model=model,prompt='Conceptual research illustration, not a measured chart or forensic evidence. '+prompt,size='1024x1024',n=1)
    return base64.b64decode(response.data[0].b64_json)

def speech(key,text,model):
    return client(key).audio.speech.create(model=model,voice='alloy',input=text[:4000],response_format='mp3').read()

def start_video(key,prompt,model):
    return client(key).videos.create(model=model,prompt='Conceptual illustration, not forensic reconstruction. '+prompt,seconds='4',size='1280x720').model_dump()

def poll_video(key,job):
    api=client(key);result=api.videos.retrieve(job).model_dump()
    return result,(api.videos.download_content(job).read() if result['status']=='completed' else None)

def error_text(exc):
    # Never expose request bodies or credentials.
    code=getattr(exc,'code',None);status=getattr(exc,'status_code',None)
    return f'{type(exc).__name__}; HTTP {status or "n/a"}; code {code or "n/a"}. Check project billing/quota for insufficient_quota; retry later for rate_limit_exceeded; check model access for model_not_found.'
