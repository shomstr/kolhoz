import { Suspense,lazy,useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2,AlertCircle,X } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useGreenhouseStore } from '../../store/useGreenhouseStore';
import { api } from '../../api/client';
import { Loading } from '../ui/UI';
import type { NavigationPage } from '../../types';
const pages={overview:lazy(()=>import('../../pages/OverviewPage').then(m=>({default:m.OverviewPage}))),climate:lazy(()=>import('../../pages/ClimatePage').then(m=>({default:m.ClimatePage}))),experiments:lazy(()=>import('../../pages/ExperimentsPage').then(m=>({default:m.ExperimentsPage}))),data:lazy(()=>import('../../pages/ModelDataPage').then(m=>({default:m.ModelDataPage}))),economics:lazy(()=>import('../../pages/EconomicsPage').then(m=>({default:m.EconomicsPage}))),reports:lazy(()=>import('../../pages/ReportsPage').then(m=>({default:m.ReportsPage}))),settings:lazy(()=>import('../../pages/SettingsPage').then(m=>({default:m.SettingsPage})))};
export function MainLayout(){
 const {activePage,setActivePage,setApiStatus,setCurrentClimate,isSidebarOpen,setSidebarOpen,notification,notificationKind,setNotification}=useGreenhouseStore();
 const health=useQuery({queryKey:['health'],queryFn:api.getHealth,refetchInterval:30000,retry:1});
 const current=useQuery({queryKey:['climate-current'],queryFn:api.getCurrentClimate,refetchInterval:30000});
 useEffect(()=>{setApiStatus(health.isPending?'checking':health.isError?'offline':'online');},[health.isPending,health.isError,setApiStatus]);
 useEffect(()=>{if(current.data)setCurrentClimate(current.data);},[current.data,setCurrentClimate]);
 useEffect(()=>{const sync=()=>{const page=location.hash.replace(/^#\/?/,'');if(page in pages)setActivePage(page as NavigationPage);};window.addEventListener('hashchange',sync);window.addEventListener('popstate',sync);return()=>{window.removeEventListener('hashchange',sync);window.removeEventListener('popstate',sync);};},[setActivePage]);
 useEffect(()=>{if(location.hash!==`#/${activePage}`)history.pushState(null,'',`#/${activePage}`);document.querySelector('main')?.scrollTo({top:0});},[activePage]);
 useEffect(()=>{if(!notification)return;const t=setTimeout(()=>setNotification(null),6500);return()=>clearTimeout(t);},[notification,setNotification]);
 const Page=pages[activePage];
 return <div className="app-shell"><a className="skip-link" href="#workspace">К основному содержимому</a><Sidebar mobileOpen={isSidebarOpen} onNavigate={()=>setSidebarOpen(false)}/><div className="app-workspace"><Header/><main id="workspace" className={`workspace page-${activePage}`}><Suspense fallback={<Loading/>}><Page/></Suspense></main></div>{notification&&<div className={`toast-message ${notificationKind}`} role={notificationKind==='error'?'alert':'status'}>{notificationKind==='error'?<AlertCircle size={20}/>:<CheckCircle2 size={20}/>}<span>{notification}</span><button aria-label="Закрыть уведомление" onClick={()=>setNotification(null)}><X size={18}/></button></div>}</div>;
}
