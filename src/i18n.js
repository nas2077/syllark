/* Local, synchronous translations: switching language never reloads the page. */
(function () {
  "use strict";
  const catalogs=window.APP_TRANSLATIONS;
  const languages=window.APP_LANGUAGES;
  let locale="en", patterns=[], cache=new Map(), insensitive={};
  let pluralRule=new Intl.PluralRules("en");
  const formats=new Map();
  const bindings=new WeakMap();
  const escape=s=>s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
  function normalize(code){
    if(catalogs[code]) return code;
    const base=String(code||"").toLowerCase().split(/[-_]/)[0];
    return languages.find(l=>l.code.toLowerCase().split("-")[0]===base)?.code||"en";
  }
  function text(source, depth=0){
    if(source==null) return "";
    source=String(source);
    if(depth>5) return source;
    if(cache.has(source)) return cache.get(source);
    const catalog=catalogs[locale];
    let translated=catalog[source]??catalog[insensitive[source.toLowerCase()]];
    if(translated==null) {
      for(const {key,re,names} of patterns){
        const m=re.exec(source);
        if(!m) continue;
        const args=Object.fromEntries(names.map((name,i)=>[name,text(m[i+1],depth+1)]));
        const forms=window.APP_PLURALS?.[locale]?.[key];
        const count=Number(m[names.indexOf(forms?.arg||"p0")+1]);
        const template=forms?.[pluralRule.select(count)]??catalog[key];
        translated=template.replace(/\{(\w+)\}/g,(_,name)=>{
          const value=args[name]??"{"+name+"}";
          return locale==="ar"?"\u2068"+value+"\u2069":value;
        });
        break;
      }
    }
    // External errors and video captions retain their original wording.
    if(translated==null && /\n| · /.test(source))
      translated=source.split(/(\n| · )/).map(p=>p==="\n"||p===" · "?p:text(p,depth+1)).join("");
    translated=translated??source;
    if(source[0] && source[0]!==source[0].toLocaleLowerCase() && source[0]===source[0].toLocaleUpperCase())
      translated=translated.charAt(0).toLocaleUpperCase(locale)+translated.slice(1);
    if(cache.size>=2000) cache.clear();
    cache.set(source,translated);
    return translated;
  }
  function set(el, source, attribute="textContent"){
    source=String(source??"");
    let b=bindings.get(el);
    if(!b){ b=new Map(); bindings.set(el,b); }
    b.set(attribute,source);
    el.dataset.localized="";
    if(attribute==="textContent") el.textContent=text(source);
    else el.setAttribute(attribute,text(source));
  }
  function apply(root=document){
    root.querySelectorAll("[data-i18n]").forEach(el=>set(el,el.dataset.i18n));
    root.querySelectorAll("[data-i18n-title]").forEach(el=>set(el,el.dataset.i18nTitle,"title"));
    root.querySelectorAll("[data-i18n-aria]").forEach(el=>set(el,el.dataset.i18nAria,"aria-label"));
    root.querySelectorAll("[data-localized]").forEach(el=>{
      for(const [attribute,source] of bindings.get(el)||[]){
        if(attribute==="textContent") el.textContent=text(source);
        else el.setAttribute(attribute,text(source));
      }
    });
  }
  function change(code){
    locale=normalize(code); cache.clear();
    pluralRule=new Intl.PluralRules(locale);
    const keys=Object.keys(catalogs.en);
    insensitive=Object.fromEntries(keys.map(key=>[key.toLowerCase(),key]));
    patterns=keys.filter(k=>/\{\w+\}/.test(k)).sort((a,b)=>b.length-a.length).map(key=>{
      const names=[];
      const chunks=key.split(/(\{\w+\})/g);
      const pattern=chunks.map(chunk=>{
        if(/^\{\w+\}$/.test(chunk)){ names.push(chunk.slice(1,-1)); return "([\\s\\S]*?)"; }
        return escape(chunk);
      }).join("");
      return {key,names,re:new RegExp("^"+pattern+"$","i")};
    });
    document.documentElement.lang=locale;
    document.documentElement.dir=locale==="ar"?"rtl":"ltr";
    apply();
    document.dispatchEvent(new CustomEvent("uilanguagechange",{detail:locale}));
  }
  function number(value, options={}){
    const key=locale+JSON.stringify(options);
    if(!formats.has(key))formats.set(key,new Intl.NumberFormat(locale,options));
    return formats.get(key).format(value);
  }
  window.I18n={text,set,apply,change,normalize,languages,number,get locale(){return locale;}};
})();
