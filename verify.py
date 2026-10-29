"""Black-box integration checks against real PostgreSQL. Uses Python standard library."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import threading
import urllib.error
import urllib.request
from uuid import uuid4

ROOT = Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-url',default='http://127.0.0.1:8083')
    parser.add_argument('--persistence',action='store_true')
    parser.add_argument('--report',default='docs/verification-results.json')
    args=parser.parse_args()
    env=dict(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if line and not line.startswith('#'))
    admin={'X-Admin-Key':env['ADMIN_API_KEY']}
    checks=[]
    def api(path,method='GET',data=None,expected=200,headers=None):
        req=urllib.request.Request(args.base_url+path,method=method,data=json.dumps(data).encode() if data is not None else None,
            headers={'Content-Type':'application/json',**(headers or {})})
        try:response=urllib.request.urlopen(req,timeout=20)
        except urllib.error.HTTPError as e:response=e
        with response:
            body=response.read()
            assert response.status==expected,(method,path,response.status,expected,body.decode()[:400])
            checks.append({'method':method,'path':path,'status':response.status})
            if not body:return None
            return json.loads(body) if 'json' in response.headers.get('Content-Type','') else body.decode()
    def compose(*cmd,capture=False):
        r=subprocess.run(['docker','compose',*cmd],cwd=ROOT,check=True,capture_output=capture,text=True)
        return r.stdout.strip() if capture else None
    def token(b):return {'X-Booking-Token':b['manage_token']}
    def payload(flight,seat='1A',fare='light'):
        return {'flight_id':flight,'seat':seat,'fare':fare,'passenger_name':'Alex Morgan','email':'alex@example.com','request_key':str(uuid4())}
    def remove(b):
        api('/api/bookings/'+b['id']+'/cancel','POST',headers=token(b))
        api('/api/bookings/'+b['id'],'DELETE',expected=204,headers=token(b))
    assert 'Aeron' in api('/')
    assert 'chooseFlight' in api('/static/app.js')
    assert '.flight-card' in api('/static/style.css')
    assert api('/health')['database']=='connected'
    assert len(api('/api/airports'))==6
    assert api('/openapi.json')['info']['title']=='Aeron Flight Booking API'
    api('/docs');api('/redoc')
    api('/api/flights?origin=XXX',expected=422)
    api('/api/flights?origin=ALA&destination=ALA',expected=422)
    api('/api/flights?limit=101',expected=422)
    api('/api/flights?sort=invalid',expected=422)
    page=api('/api/flights?origin=ALA&destination=NQZ&sort=price&limit=2')
    assert len(page['flights'])==2 and page['total']>=3
    assert page['flights'][0]['price_kzt']<=page['flights'][1]['price_kzt']
    assert api('/api/flights?limit=1&offset=1')['flights'][0]['id']!=api('/api/flights?limit=1')['flights'][0]['id']
    departure=datetime.now(timezone.utc)+timedelta(days=30)
    flight={'number':'AE'+str(9000+uuid4().int%1000),'origin_code':'ALA','destination_code':'NQZ',
        'departure_at':departure.isoformat(),'arrival_at':(departure+timedelta(minutes=100)).isoformat(),'price_kzt':20001}
    api('/api/flights','POST',flight,expected=401)
    api('/api/flights','POST',{**flight,'price_kzt':-1},expected=422,headers=admin)
    api('/api/flights','POST',{**flight,'origin_code':'XXX'},expected=422,headers=admin)
    api('/api/flights','POST',{**flight,'arrival_at':departure.isoformat()},expected=422,headers=admin)
    api('/api/flights','POST',{**flight,'departure_at':'2020-01-01T00:00:00Z'},expected=422,headers=admin)
    f=api('/api/flights','POST',flight,201,admin);fid=f['id'];path='/api/flights/'+str(fid)
    assert f['available_seats']==24
    api('/api/flights','POST',flight,409,admin)
    assert api(path)['price_kzt']==20001
    f=api(path,'PUT',{**flight,'price_kzt':20003},headers=admin)
    assert f['price_kzt']==20003
    assert len(api(path+'/seats')['seats'])==24
    create=payload(fid,'1A','standard')
    api('/api/bookings','POST',{**create,'total_kzt':1},422)
    api('/api/bookings','POST',{**create,'email':'invalid'},422)
    api('/api/bookings','POST',{**create,'seat':'7A'},422)
    api('/api/bookings','POST',{**create,'fare':'unknown'},422)
    b=api('/api/bookings','POST',create,201);bp='/api/bookings/'+b['id'];bt=token(b)
    assert b['total_kzt']==25004 and b['status']=='confirmed'
    replay=api('/api/bookings','POST',create)
    assert replay['id']==b['id'] and replay['manage_token']==b['manage_token']
    api('/api/bookings','POST',{**create,'seat':'1B'},409)
    api('/api/bookings','POST',payload(fid,'1A'),409)
    api(bp,expected=401);api(bp,expected=401,headers={'X-Booking-Token':'wrong'})
    api('/api/bookings',expected=401)
    listed=api('/api/bookings?limit=100',headers=admin)
    assert any(item['id']==b['id'] for item in listed['bookings']) and 'manage_token' not in str(listed)
    assert api(bp,headers=bt)['reference']==b['reference']
    assert 'not a real ticket' in api(bp+'/itinerary',headers=bt)
    assert api(path)['available_seats']==23
    api(path,'PUT',flight,409,admin);api(path,'DELETE',expected=409,headers=admin)
    api(bp,'DELETE',expected=409,headers=bt)
    api(bp,'PUT',{'passenger_name':'Alex Taylor'},422,bt)
    api(bp,'PUT',{'passenger_name':'Alex\nTaylor','email':'alex@example.com'},422,bt)
    api(bp,'PATCH',{'passenger_name':'Alex\nTaylor'},422,bt)
    assert api(bp,'PUT',{'passenger_name':'Alex Taylor','email':'taylor@example.com'},headers=bt)['passenger_name']=='Alex Taylor'
    api(bp,'PATCH',{},422,bt);api(bp,'PATCH',{'seat':None},422,bt)
    assert api(bp,'PATCH',{'seat':'2D'},headers=bt)['seat']=='2D'
    assert next(s for s in api(path+'/seats')['seats'] if s['label']=='1A')['available']
    other=api('/api/bookings','POST',payload(fid,'3A','flex'),201)
    assert other['total_kzt']==30005
    api(bp,'PATCH',{'seat':'3A'},409,bt)
    # Real competing HTTP requests, separate DB transactions; exactly one seat winner.
    barrier=threading.Barrier(2)
    def race(_):
        data=payload(fid,'4A');barrier.wait()
        req=urllib.request.Request(args.base_url+'/api/bookings',data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        try:r=urllib.request.urlopen(req,timeout=20)
        except urllib.error.HTTPError as e:r=e
        with r:return r.status,json.loads(r.read())
    with ThreadPoolExecutor(max_workers=2) as pool:races=list(pool.map(race,range(2)))
    assert sorted(r[0] for r in races)==[201,409],races
    winner=next(r[1] for r in races if r[0]==201)
    checks.append({'check':'simultaneous same-seat requests','statuses':[r[0] for r in races]})
    remove(winner)
    if args.persistence:
        count=api('/api/flights?limit=1')['total']
        compose('down')
        compose('up','-d','--wait','--wait-timeout','180')
        assert api(bp,headers=bt)['seat']=='2D'
        assert not next(s for s in api(path+'/seats')['seats'] if s['label']=='2D')['available']
        assert api('/api/flights?limit=1')['total']==count
        checks.append({'check':'booking, occupied seat and seed count survive container recreation','passed':True})
    assert compose('exec','-T','backend','id','-u',capture=True)=='10001'
    assert compose('exec','-T','backend','python','-c','from pathlib import Path; print(Path("/app/.env").exists())',capture=True)=='False'
    assert api(bp+'/cancel','POST',headers=bt)['status']=='cancelled'
    assert api(bp+'/cancel','POST',headers=bt)['status']=='cancelled'
    api(bp,'PATCH',{'seat':'1B'},409,bt)
    replacement=api('/api/bookings','POST',payload(fid,'2D'),201)
    assert replacement['total_kzt']==20003
    remove(replacement);remove(other)
    api(bp,'DELETE',expected=204,headers=bt);api(bp,expected=404,headers=bt)
    api(path,'DELETE',expected=204,headers=admin);api(path,expected=404)
    report={'application':'Aeron','passed':True,'checks':len(checks),'persistence':args.persistence,'results':checks}
    target=ROOT/args.report;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(f'PASS: {len(checks)} checks; concurrency, ownership, idempotency, CRUD'+(', persistence' if args.persistence else ''))

if __name__=='__main__':main()
