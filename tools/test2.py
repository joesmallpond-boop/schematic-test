import numpy as np
from test import run, SR, db
n=SR
imp=np.zeros(n); imp[SR//2]=0.0005
for dset in [0.0,0.5,1.0]:
    p=dict(distortion=dset,octave=0,clipmode=1,filter=0,amps=1,boost_on=0)
    h=run(imp,p)[:,0]-run(np.zeros(n),p)[:,0]
    h=h[SR//2-50:]
    H=np.fft.rfft(h,SR)/0.0005; fr=np.fft.rfftfreq(SR,1/SR)
    Rd=100000*(np.exp(4.394*dset)-1)/(np.exp(4.394)-1)+1
    w=2j*np.pi*fr
    G=1+ (Rd/(1+w*Rd*100e-12))*(w*4.7e-6/(1+w*560*4.7e-6)+w*2.2e-6/(1+w*47*2.2e-6))
    out=[]
    for f in [50,100,500,1000,3000,8000,15000]:
        i=np.argmin(abs(fr-f)); out.append(f'{f}:{db(abs(H[i])):5.1f}/{db(abs(G[i])):5.1f}')
    print(f'dist={dset} Rd={Rd:.0f}: model/ideal  '+' '.join(out))
