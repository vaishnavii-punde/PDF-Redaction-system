import { useState, useEffect } from 'react'
import React from 'react'

const API = 'http://localhost:8000'
const ALL_CATS = ['phone','email','dob','pan','aadhaar','ssn','passport','credit','ip','voter_id','driving_licence','epic','ifsc','gst','person']

export default function App() {
  const [tab, setTab] = useState('single')
  const [file, setFile] = useState(null)
  const [fileType, setFileType] = useState(null)
  const [batchFiles, setBatchFiles] = useState([])
  const [analysis, setAnalysis] = useState(null)
  const [removedIndices, setRemovedIndices] = useState([])
  const [batchResult, setBatchResult] = useState(null)
  const [confirmed, setConfirmed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState(null)
  const [categories, setCategories] = useState(['phone','email','dob','pan','aadhaar','ssn','passport','credit','ip'])
  const [customWord, setCustomWord] = useState('')
  const [customWords, setCustomWords] = useState([])
  const [hoveredHighlight, setHoveredHighlight] = useState(null)
  const [profiles, setProfiles] = useState({})
  const [profileName, setProfileName] = useState('')
  const [showSaveProfile, setShowSaveProfile] = useState(false)
  const [profileMsg, setProfileMsg] = useState('')
  const [style, setStyle] = useState('blackbar')
  const [customLabel, setCustomLabel] = useState('[REDACTED]')
  const [minConfidence, setMinConfidence] = useState(0)

  useEffect(() => { fetchProfiles() }, [])

  async function fetchProfiles() {
    try { const res = await fetch(API+'/profiles'); setProfiles(await res.json()) } catch(e) {}
  }

  function loadProfile(name) {
    const p = profiles[name]; if (!p) return
    setCategories(p.categories); setCustomWords(p.custom_words||[])
    setProfileMsg('Loaded: '+name); setTimeout(()=>setProfileMsg(''),2000)
  }

  async function saveProfile() {
    if (!profileName.trim()) return
    await fetch(API+'/profiles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:profileName.trim(),categories,custom_words:customWords})})
    setProfileName(''); setShowSaveProfile(false); setProfileMsg('Saved!'); setTimeout(()=>setProfileMsg(''),2000); fetchProfiles()
  }

  async function deleteProfile(name) { await fetch(API+'/profiles/'+encodeURIComponent(name),{method:'DELETE'}); fetchProfiles() }

  function toggleCat(cat) { setCategories(prev=>prev.includes(cat)?prev.filter(c=>c!==cat):[...prev,cat]) }

  function getFileType(f) {
    if (!f) return null
    const n = f.name.toLowerCase()
    if (n.endsWith('.pdf')) return 'pdf'
    if (['.png','.jpg','.jpeg','.webp'].some(e=>n.endsWith(e))) return 'image'
    if (['.xlsx','.xls','.csv'].some(e=>n.endsWith(e))) return 'excel'
    return null
  }

  function handleFileSelect(f) {
    if (!f) return
    const t = getFileType(f)
    if (!t) { setError('Unsupported file. Use PDF, PNG, JPG, XLSX or CSV'); return }
    setFile(f); setFileType(t); setAnalysis(null); setConfirmed(false); setError(null); setRemovedIndices([])
  }

  function removeItem(idx) { setRemovedIndices(prev=>[...prev,idx]) }
  function restoreItem(idx) { setRemovedIndices(prev=>prev.filter(i=>i!==idx)) }

  const activeFindings = analysis ? analysis.findings.filter((_,i)=>!removedIndices.includes(i)) : []

  async function handleAnalyze() {
    if (!file) return
    setLoading(true); setError(null); setAnalysis(null); setConfirmed(false); setRemovedIndices([])
    const form = new FormData()
    form.append('file',file); form.append('categories',categories.join(','))
    form.append('custom_words',customWords.join(',')); form.append('min_confidence',minConfidence/100)
    try {
      const ep = fileType==='excel'?'/analyze-excel':fileType==='image'?'/analyze-image':'/analyze'
      const res = await fetch(API+ep,{method:'POST',body:form})
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setAnalysis(data)
    } catch(e) { setError(e.message) }
    finally { setLoading(false) }
  }

  async function handleConfirm() {
    if (!analysis) return
    setConfirming(true)
    try {
      const params = new URLSearchParams({style, custom_label:customLabel, removed_indices:removedIndices.join(',')})
      const res = await fetch(API+'/confirm/'+analysis.file_id+'?'+params.toString(),{method:'POST'})
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setConfirmed(true)
    } catch(e) { setError(e.message) }
    finally { setConfirming(false) }
  }

  async function handleBatch() {
    if (!batchFiles.length) return
    setLoading(true); setError(null); setBatchResult(null)
    const form = new FormData()
    batchFiles.forEach(f=>form.append('files',f))
    form.append('categories',categories.join(',')); form.append('custom_words',customWords.join(','))
    form.append('style',style); form.append('custom_label',customLabel); form.append('min_confidence',minConfidence/100)
    try {
      const res = await fetch(API+'/batch',{method:'POST',body:form})
      const data = await res.json()
      if (data.error) throw new Error(data.error)
      setBatchResult(data)
    } catch(e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const e = React.createElement
  const typeColor = {pdf:'#5C7CB9',image:'#10b981',excel:'#f59e0b'}
  const typeIcon = {pdf:'📄',image:'🖼️',excel:'📊'}

  const s = {
    page:{minHeight:'100vh',background:'linear-gradient(135deg,#1F4959 0%,#242424 60%,#1F4959 100%)',fontFamily:'Segoe UI,sans-serif',paddingBottom:60},
    nav:{background:'rgba(36,36,36,0.95)',borderBottom:'1px solid #5C7CB9',padding:'18px 40px',display:'flex',alignItems:'center',justifyContent:'space-between'},
    card:{background:'rgba(36,36,36,0.85)',border:'1px solid #5C7CB9',borderRadius:16,padding:'28px 32px',marginBottom:20},
    input:{flex:1,padding:'10px 14px',border:'1px solid #5C7CB9',borderRadius:8,fontSize:13,background:'rgba(31,73,89,0.3)',color:'#FFFFFF',outline:'none'},
    btn:(off,col)=>({padding:'14px 28px',background:off?'rgba(92,124,185,0.3)':col||'linear-gradient(90deg,#1F4959,#5C7CB9)',color:off?'#5C7CB9':'#fff',border:'none',borderRadius:10,fontWeight:700,fontSize:15,cursor:off?'not-allowed':'pointer'}),
    tabBtn:(on)=>({padding:'10px 28px',borderRadius:10,border:'1px solid #5C7CB9',cursor:'pointer',fontWeight:700,fontSize:14,background:on?'#5C7CB9':'transparent',color:'#fff'}),
    badge:(col)=>({display:'inline-block',padding:'2px 10px',borderRadius:20,fontSize:11,fontWeight:700,background:col,color:'#fff',marginRight:6}),
    catBtn:(on,warn)=>({padding:'6px 14px',borderRadius:20,cursor:'pointer',fontSize:11,fontWeight:700,textTransform:'uppercase',border:'1px solid '+(on?(warn?'#f59e0b':'#5C7CB9'):'rgba(92,124,185,0.3)'),background:on?(warn?'rgba(245,158,11,0.2)':'#5C7CB9'):'transparent',color:on?(warn?'#f59e0b':'#fff'):'#5C7CB9'}),
    styleCard:(on)=>({flex:1,padding:14,borderRadius:12,border:'2px solid '+(on?'#fff':'rgba(92,124,185,0.4)'),cursor:'pointer',background:on?'rgba(92,124,185,0.25)':'rgba(31,73,89,0.2)',textAlign:'center',minWidth:100})
  }

  const STYLE_OPTIONS = [
    {key:'blackbar',label:'Black Bar',preview:e('div',{style:{background:'#000',height:14,borderRadius:2,width:'80%',margin:'0 auto 8px'}})},
    {key:'text',label:'Label',preview:e('div',{style:{color:'#333',fontWeight:600,fontSize:12,background:'#f5f5f5',borderRadius:3,padding:'1px 6px',display:'inline-block',marginBottom:8}},customLabel||'[REDACTED]')},
    {key:'blur',label:'Blur',preview:e('div',{style:{background:'repeating-linear-gradient(45deg,#888 0,#888 2px,#aaa 2px,#aaa 4px)',height:14,borderRadius:2,width:'80%',margin:'0 auto 8px'}})},
    {key:'strikethrough',label:'Strikethrough',preview:e('div',{style:{position:'relative',height:14,marginBottom:8}},e('div',{style:{background:'rgba(255,255,255,0.2)',height:14,borderRadius:2,width:'80%',margin:'0 auto'}}),e('div',{style:{position:'absolute',top:'50%',left:'10%',right:'10%',height:2,background:'#ef4444'}}))}
  ]

  const styleSelector = e('div',{style:s.card},
    e('div',{style:{color:'#fff',fontWeight:600,marginBottom:16,fontSize:15}},'Redaction Style'),
    e('div',{style:{display:'flex',gap:10,flexWrap:'wrap',marginBottom:14}},
      ...STYLE_OPTIONS.map(opt=>e('div',{key:opt.key,onClick:()=>setStyle(opt.key),style:s.styleCard(style===opt.key)},
        opt.preview,
        e('div',{style:{color:'#fff',fontWeight:700,fontSize:12}},opt.label)
      ))
    ),
    (style==='text')&&e('div',{style:{display:'flex',gap:8,alignItems:'center',marginTop:8}},
      e('span',{style:{color:'#94a3b8',fontSize:13,whiteSpace:'nowrap'}},'Custom label:'),
      e('input',{value:customLabel,onChange:ev=>setCustomLabel(ev.target.value),placeholder:'[REDACTED]',
        style:{...s.input,flex:1,padding:'8px 12px'}})
    )
  )

  const confidenceSlider = e('div',{style:{...s.card,paddingBottom:20}},
    e('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}  ,
      e('div',{style:{color:'#fff',fontWeight:600,fontSize:15}},'Confidence Threshold'),
      e('span',{style:{background:minConfidence>=70?'#ef4444':minConfidence>=40?'#f59e0b':'#10b981',color:'#fff',padding:'3px 12px',borderRadius:20,fontSize:13,fontWeight:700}},
        minConfidence===0?'All detections':('Min '+minConfidence+'%'))
    ),
    e('input',{type:'range',min:0,max:95,step:5,value:minConfidence,
      onChange:ev=>setMinConfidence(Number(ev.target.value)),
      style:{width:'100%',accentColor:'#5C7CB9'}}),
    e('div',{style:{display:'flex',justifyContent:'space-between',color:'#5C7CB9',fontSize:11,marginTop:4}},
      e('span',null,'0% — show all'),
      e('span',null,'50% — medium'),
      e('span',null,'95% — very high only')
    )
  )

  const profilesPanel = e('div',{style:s.card},
    e('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}},
      e('div',{style:{color:'#fff',fontWeight:600,fontSize:15}},'Redaction Profiles'),
      e('div',{style:{display:'flex',gap:8,alignItems:'center'}},
        profileMsg&&e('span',{style:{color:'#10b981',fontSize:13}},profileMsg),
        e('button',{onClick:()=>setShowSaveProfile(!showSaveProfile),style:{padding:'6px 14px',background:'#5C7CB9',border:'none',borderRadius:8,color:'#fff',fontWeight:600,cursor:'pointer',fontSize:13}},showSaveProfile?'Cancel':'+ Save Current')
      )
    ),
    showSaveProfile&&e('div',{style:{display:'flex',gap:8,marginBottom:14}},
      e('input',{value:profileName,onChange:ev=>setProfileName(ev.target.value),onKeyDown:ev=>ev.key==='Enter'&&saveProfile(),placeholder:'Profile name...',style:{...s.input,flex:1}}),
      e('button',{onClick:saveProfile,style:{padding:'10px 18px',background:'#10b981',border:'none',borderRadius:8,color:'#fff',fontWeight:600,cursor:'pointer'}},'Save')
    ),
    Object.keys(profiles).length===0
      ?e('p',{style:{color:'#5C7CB9',fontSize:13,margin:0}},'No profiles yet.')
      :e('div',{style:{display:'flex',flexWrap:'wrap',gap:10}},
          ...Object.entries(profiles).map(([name,p])=>
            e('div',{key:name,style:{background:'rgba(31,73,89,0.5)',border:'1px solid rgba(92,124,185,0.4)',borderRadius:10,padding:'12px 16px',minWidth:180}},
              e('div',{style:{color:'#fff',fontWeight:600,fontSize:14,marginBottom:6}},name),
              e('div',{style:{color:'#5C7CB9',fontSize:12,marginBottom:10}},p.categories.length+' categories'),
              e('div',{style:{display:'flex',gap:6}},
                e('button',{onClick:()=>loadProfile(name),style:{flex:1,padding:'6px 10px',background:'#5C7CB9',border:'none',borderRadius:6,color:'#fff',fontWeight:600,cursor:'pointer',fontSize:12}},'Load'),
                e('button',{onClick:()=>deleteProfile(name),style:{padding:'6px 10px',background:'rgba(239,68,68,0.2)',border:'1px solid rgba(239,68,68,0.4)',borderRadius:6,color:'#ef4444',fontWeight:600,cursor:'pointer',fontSize:12}},'Del')
              )
            )
          )
        )
  )

  const categoriesPanel = e('div',{style:s.card},
    e('div',{style:{color:'#fff',fontWeight:600,marginBottom:4,fontSize:15}},'Categories'),
    e('div',{style:{color:'#94a3b8',fontSize:11,marginBottom:12}},'New: VOTER ID, DRIVING LICENCE, EPIC, IFSC, GST added | PERSON off by default'),
    e('div',{style:{display:'flex',flexWrap:'wrap',gap:7,marginBottom:14}},
      ...ALL_CATS.map(cat=>{
        const warn=cat==='person'; const on=categories.includes(cat)
        return e('button',{key:cat,onClick:()=>toggleCat(cat),style:s.catBtn(on,warn)},
          warn?'⚠ PERSON':cat.replace('_',' ').toUpperCase())
      })
    ),
    e('div',{style:{display:'flex',gap:8}},
      e('input',{value:customWord,onChange:ev=>setCustomWord(ev.target.value),
        onKeyDown:ev=>{if(ev.key==='Enter'&&customWord.trim()){setCustomWords(p=>[...p,customWord.trim()]);setCustomWord('')}},
        placeholder:'Custom word...',style:s.input}),
      e('button',{onClick:()=>{if(customWord.trim()){setCustomWords(p=>[...p,customWord.trim()]);setCustomWord('')}},
        style:{padding:'10px 18px',background:'#5C7CB9',border:'none',borderRadius:8,color:'#fff',fontWeight:600,cursor:'pointer'}},'+ Add')
    ),
    customWords.length>0&&e('div',{style:{display:'flex',gap:6,flexWrap:'wrap',marginTop:10}},
      ...customWords.map((w,i)=>e('span',{key:i,style:{background:'rgba(92,124,185,0.2)',border:'1px solid #5C7CB9',color:'#fff',padding:'3px 10px',borderRadius:20,fontSize:12}},
        w,e('span',{onClick:()=>setCustomWords(p=>p.filter((_,j)=>j!==i)),style:{cursor:'pointer',marginLeft:6,color:'#5C7CB9'}},'x')
      ))
    )
  )

  const uploadCard = e('div',{style:s.card},
    e('div',{style:{color:'#fff',fontWeight:600,marginBottom:8,fontSize:15}},'Upload File'),
    e('div',{style:{display:'flex',gap:8,marginBottom:14,flexWrap:'wrap'}},
      e('span',{style:s.badge('#5C7CB9')},'📄 PDF'),
      e('span',{style:s.badge('#10b981')},'🖼️ PNG / JPG'),
      e('span',{style:s.badge('#f59e0b')},'📊 XLSX / CSV')
    ),
    e('div',{
      onDrop:ev=>{ev.preventDefault();handleFileSelect(ev.dataTransfer.files[0])},
      onDragOver:ev=>ev.preventDefault(),
      onClick:()=>document.getElementById('fileinput').click(),
      style:{border:'2px dashed #5C7CB9',borderRadius:12,padding:'40px',textAlign:'center',cursor:'pointer',background:'rgba(31,73,89,0.3)'}
    },
      e('input',{id:'fileinput',type:'file',accept:'.pdf,.png,.jpg,.jpeg,.webp,.xlsx,.xls,.csv',style:{display:'none'},onChange:ev=>handleFileSelect(ev.target.files[0])}),
      e('div',{style:{fontSize:44,marginBottom:10}},file?typeIcon[fileType]:'📂'),
      file
        ?e('div',null,e('p',{style:{color:'#fff',fontWeight:600,margin:'0 0 8px'}},file.name),e('span',{style:s.badge(typeColor[fileType]||'#5C7CB9')},fileType.toUpperCase()))
        :e('div',null,e('p',{style:{color:'#fff',fontWeight:600,margin:'0 0 4px'}},'Drop file here'),e('p',{style:{color:'#5C7CB9',fontSize:13,margin:0}},'PDF, PNG, JPG, XLSX or CSV'))
    )
  )

  const detectedPanel = analysis&&!confirmed&&e('div',null,
    e('div',{style:{...s.card,borderColor:activeFindings.length>0?'#f59e0b':'#5C7CB9'}},
      e('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}},
        e('span',{style:{color:'#fff',fontWeight:600,fontSize:15}},'Detected Items'),
        e('div',{style:{display:'flex',gap:8,alignItems:'center'}},
          removedIndices.length>0&&e('span',{style:{color:'#94a3b8',fontSize:12}},removedIndices.length+' removed'),
          e('span',{style:{background:activeFindings.length>0?'#f59e0b':'#5C7CB9',color:'#fff',padding:'4px 14px',borderRadius:20,fontSize:13,fontWeight:700}},activeFindings.length+' will redact')
        )
      ),
      analysis.findings.length===0
        ?e('p',{style:{color:'#5C7CB9',textAlign:'center'}},'No sensitive data detected.')
        :e('div',{style:{maxHeight:260,overflowY:'auto'}},
            ...analysis.findings.map((f,i)=>{
              const removed=removedIndices.includes(i)
              return e('div',{key:i,style:{display:'flex',justifyContent:'space-between',alignItems:'center',background:removed?'rgba(100,100,100,0.1)':'rgba(31,73,89,0.4)',borderRadius:8,padding:'8px 12px',marginBottom:6,border:'1px solid '+(removed?'rgba(100,100,100,0.2)':'rgba(92,124,185,0.3)'),opacity:removed?0.4:1}},
                e('span',{style:{background:f.type==='PERSON'?'rgba(245,158,11,0.2)':'#1F4959',color:f.type==='PERSON'?'#f59e0b':'#5C7CB9',padding:'2px 8px',borderRadius:20,fontSize:10,fontWeight:700,textTransform:'uppercase',flexShrink:0}},f.type),
                e('span',{style:{fontFamily:'monospace',color:removed?'#666':'#fff',fontSize:12,flex:1,textAlign:'center',textDecoration:removed?'line-through':'none',padding:'0 8px'}},f.text),
                e('span',{style:{color:'#5C7CB9',fontSize:11,marginRight:8,flexShrink:0}},Math.round(f.score*100)+'%'),
                removed
                  ?e('button',{onClick:()=>restoreItem(i),style:{padding:'2px 8px',background:'rgba(16,185,129,0.2)',border:'1px solid #10b981',borderRadius:6,color:'#10b981',fontSize:11,cursor:'pointer',flexShrink:0}},'Restore')
                  :e('button',{onClick:()=>removeItem(i),style:{padding:'2px 8px',background:'rgba(239,68,68,0.15)',border:'1px solid rgba(239,68,68,0.4)',borderRadius:6,color:'#ef4444',fontSize:11,cursor:'pointer',flexShrink:0}},'Remove')
              )
            })
          )
    ),

    analysis.preview_pages&&analysis.preview_pages.length>0&&e('div',null,
      e('div',{style:{color:'#fff',fontWeight:600,fontSize:15,marginBottom:14}},'Page Preview'),
      ...analysis.preview_pages.map((pg,pi)=>
        e('div',{key:pi,style:{...s.card,padding:16,marginBottom:16}},
          e('div',{style:{color:'#5C7CB9',fontSize:12,fontWeight:600,marginBottom:10,textTransform:'uppercase'}},
            'Page '+(pi+1)+'  —  '+activeFindings.filter(f=>f.page===pi).length+' redactions'),
          e('div',{style:{position:'relative',display:'inline-block',width:'100%'}},
            e('img',{src:'data:image/png;base64,'+pg.image,style:{width:'100%',borderRadius:8,display:'block'}}),
            e('svg',{style:{position:'absolute',top:0,left:0,width:'100%',height:'100%'},viewBox:'0 0 '+pg.width+' '+pg.height,preserveAspectRatio:'none'},
              ...pg.highlights.map((h,hi)=>{
                const findingIdx=analysis.findings.findIndex(f=>f.text===h.text&&f.page===pi)
                const isRemoved=removedIndices.includes(findingIdx)
                return e('rect',{key:hi,x:h.x,y:h.y,width:h.w,height:h.h,
                  fill:isRemoved?'rgba(100,100,100,0.1)':hoveredHighlight===(pi+'-'+hi)?'rgba(245,158,11,0.5)':(style==='blackbar'?'rgba(0,0,0,0.7)':'rgba(239,68,68,0.35)'),
                  stroke:isRemoved?'rgba(100,100,100,0.3)':hoveredHighlight===(pi+'-'+hi)?'#f59e0b':(style==='blackbar'?'#000':'#ef4444'),
                  strokeWidth:1.5,rx:2,strokeDasharray:isRemoved?'4 2':'none',
                  onMouseEnter:()=>setHoveredHighlight(pi+'-'+hi),
                  onMouseLeave:()=>setHoveredHighlight(null)
                })
              })
            )
          )
        )
      )
    ),

    e('div',{style:{display:'flex',gap:12}},
      e('button',{onClick:()=>{setAnalysis(null);setFile(null);setFileType(null);setRemovedIndices([])},style:{...s.btn(false,'rgba(92,124,185,0.2)'),border:'1px solid #5C7CB9',flex:1}},'Cancel'),
      e('button',{onClick:handleConfirm,disabled:confirming||activeFindings.length===0,style:{...s.btn(confirming||activeFindings.length===0),flex:2}},
        confirming?'Applying...':'Confirm & Redact ('+activeFindings.length+' items)')
    )
  )

  const successPanel = confirmed&&e('div',{style:{...s.card,borderColor:'#10b981',textAlign:'center',padding:'40px'}},
    e('div',{style:{fontSize:52,marginBottom:16}},'🎉'),
    e('h3',{style:{color:'#fff',fontSize:22,margin:'0 0 8px'}},'Redaction Complete!'),
    e('p',{style:{color:'#5C7CB9',marginBottom:24}},'File processed successfully.'),
    e('div',{style:{display:'flex',gap:12,justifyContent:'center'}},
      e('a',{href:API+'/download/'+analysis.file_id,target:'_blank',style:{padding:'14px 32px',background:'linear-gradient(90deg,#1F4959,#5C7CB9)',color:'#fff',borderRadius:10,fontWeight:700,textDecoration:'none',fontSize:15}},'Download Redacted File'),
      e('button',{onClick:()=>{setFile(null);setFileType(null);setAnalysis(null);setConfirmed(false);setRemovedIndices([])},style:{padding:'14px 24px',background:'transparent',border:'1px solid #5C7CB9',color:'#5C7CB9',borderRadius:10,fontWeight:600,cursor:'pointer'}},'Redact Another')
    )
  )

  return e('div',{style:s.page},
    e('div',{style:s.nav},
      e('span',{style:{color:'#fff',fontSize:22,fontWeight:700}},'PDF Redactor'),
      e('span',{style:{background:'#5C7CB9',color:'#fff',fontSize:11,padding:'3px 12px',borderRadius:20}},'LOCAL & PRIVATE')
    ),
    e('div',{style:{textAlign:'center',padding:'50px 20px 30px'}},
      e('h1',{style:{color:'#fff',fontSize:40,fontWeight:700,margin:'0 0 10px'}},'Redact Sensitive Information'),
      e('p',{style:{color:'#5C7CB9',fontSize:15,margin:0}},'Remove false positives, set confidence threshold, choose redaction style')
    ),
    e('div',{style:{maxWidth:860,margin:'0 auto',padding:'0 24px'}},
      profilesPanel, styleSelector, confidenceSlider,
      e('div',{style:{display:'flex',gap:12,marginBottom:24}},
        e('button',{onClick:()=>{setTab('single');setError(null)},style:s.tabBtn(tab==='single')},'Single File'),
        e('button',{onClick:()=>{setTab('batch');setError(null)},style:s.tabBtn(tab==='batch')},'Batch Upload')
      ),
      tab==='single'&&e('div',null,
        uploadCard, categoriesPanel,
        e('button',{onClick:handleAnalyze,disabled:!file||loading,style:{...s.btn(!file||loading),width:'100%',marginBottom:20}},
          loading?'Analyzing...':'Analyze '+(fileType?fileType.toUpperCase():'File')),
        error&&e('div',{style:{padding:14,background:'rgba(255,80,80,0.1)',border:'1px solid rgba(255,80,80,0.4)',borderRadius:10,color:'#ff8080',fontSize:13,marginBottom:16}},error),
        detectedPanel, successPanel
      ),
      tab==='batch'&&e('div',null,
        e('div',{style:s.card},
          e('div',{style:{color:'#fff',fontWeight:600,marginBottom:16,fontSize:15}},'Upload Multiple Files'),
          e('div',{
            onDrop:ev=>{ev.preventDefault();setBatchFiles(Array.from(ev.dataTransfer.files));setBatchResult(null)},
            onDragOver:ev=>ev.preventDefault(),
            onClick:()=>document.getElementById('batchinput').click(),
            style:{border:'2px dashed #5C7CB9',borderRadius:12,padding:'40px',textAlign:'center',cursor:'pointer',background:'rgba(31,73,89,0.3)'}
          },
            e('input',{id:'batchinput',type:'file',accept:'.pdf,.png,.jpg,.jpeg,.xlsx,.xls,.csv',multiple:true,style:{display:'none'},onChange:ev=>{setBatchFiles(Array.from(ev.target.files));setBatchResult(null)}}),
            e('div',{style:{fontSize:40,marginBottom:10}},batchFiles.length>0?'📦':'📂'),
            batchFiles.length>0
              ?e('div',null,e('p',{style:{color:'#5C7CB9',fontWeight:600,margin:'0 0 8px'}},batchFiles.length+' files selected'),...batchFiles.map((f,i)=>e('div',{key:i,style:{color:'#fff',fontSize:13,padding:'3px 0',display:'flex',alignItems:'center',gap:8}},e('span',{style:s.badge(typeColor[getFileType(f)]||'#5C7CB9')},(getFileType(f)||'?').toUpperCase()),f.name)))
              :e('div',null,e('p',{style:{color:'#fff',fontWeight:600,margin:'0 0 4px'}},'Drop multiple files here'),e('p',{style:{color:'#5C7CB9',fontSize:13,margin:0}},'PDF, PNG, JPG, XLSX or CSV'))
          )
        ),
        categoriesPanel,
        e('button',{onClick:handleBatch,disabled:!batchFiles.length||loading,style:{...s.btn(!batchFiles.length||loading),width:'100%',marginBottom:20}},
          loading?'Processing...':'Redact All '+(batchFiles.length||'')+' Files'),
        error&&e('div',{style:{padding:14,background:'rgba(255,80,80,0.1)',border:'1px solid rgba(255,80,80,0.4)',borderRadius:10,color:'#ff8080',fontSize:13,marginBottom:16}},error),
        batchResult&&e('div',{style:{...s.card,borderColor:'#10b981'}},
          e('div',{style:{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:20}},
            e('h3',{style:{color:'#fff',margin:0,fontSize:18}},'Batch Complete'),
            e('div',{style:{display:'flex',gap:8}},
              e('span',{style:{background:'#10b981',color:'#fff',padding:'4px 12px',borderRadius:20,fontSize:12,fontWeight:700}},batchResult.success+' done'),
              batchResult.failed>0&&e('span',{style:{background:'#ef4444',color:'#fff',padding:'4px 12px',borderRadius:20,fontSize:12,fontWeight:700}},batchResult.failed+' failed')
            )
          ),
          e('div',{style:{marginBottom:20}},
            ...batchResult.results.map((r,i)=>e('div',{key:i,style:{display:'flex',justifyContent:'space-between',alignItems:'center',background:r.status==='done'?'rgba(16,185,129,0.1)':'rgba(239,68,68,0.1)',border:'1px solid '+(r.status==='done'?'rgba(16,185,129,0.3)':'rgba(239,68,68,0.3)'),borderRadius:8,padding:'10px 14px',marginBottom:8}},
              e('span',{style:{color:'#fff',fontSize:13}},r.filename),
              e('span',{style:{color:r.status==='done'?'#10b981':'#ef4444',fontSize:12,fontWeight:600}},r.status==='done'?r.count+' redacted':'Error')
            ))
          ),
          e('a',{href:API+'/download-batch/'+batchResult.batch_id,target:'_blank',style:{display:'inline-block',padding:'14px 32px',background:'linear-gradient(90deg,#1F4959,#5C7CB9)',color:'#fff',borderRadius:10,fontWeight:700,textDecoration:'none',fontSize:15}},'Download All as ZIP'),
          e('button',{onClick:()=>{setBatchFiles([]);setBatchResult(null)},style:{marginLeft:12,padding:'14px 24px',background:'transparent',border:'1px solid #5C7CB9',color:'#5C7CB9',borderRadius:10,fontWeight:600,cursor:'pointer'}},'Clear')
        )
      )
    )
  )
}
