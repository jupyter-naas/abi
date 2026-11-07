/**
 * During a view the browser keeps nothing and reads nothing it kept (see `view-flag`): this script
 * runs in the page's head, before any store is created, and puts an in-memory storage in place of
 * `localStorage` and `sessionStorage` for that page load. Everything that persists through them
 * (the stores, the preferences, the theme) then starts empty and leaves nothing behind. It is plain
 * ES5 text so it can be inlined; tests run it against a fake window. The browser's own
 * `localStorage` is kept aside for one use: a sign-out in a view still clears the stores it must
 * (nothing is read from it, nothing is written to it).
 */
export const VIEW_STORAGE_GUARD = `(function(){try{
var name=${JSON.stringify('nexus-view-as')};
if(document.cookie.split(';').every(function(c){return c.trim().split('=')[0]!==name;}))return;
document.documentElement.setAttribute('data-view-as','');
try{Object.defineProperty(window,'__nexusRealLocalStorage',{value:window.localStorage,configurable:true});}catch(e){}
function memory(){var data={};return{
getItem:function(k){return Object.prototype.hasOwnProperty.call(data,k)?data[k]:null;},
setItem:function(k,v){data[k]=String(v);},
removeItem:function(k){delete data[k];},
clear:function(){data={};},
key:function(i){return Object.keys(data)[i]||null;},
get length(){return Object.keys(data).length;}};}
['localStorage','sessionStorage'].forEach(function(n){
try{Object.defineProperty(window,n,{value:memory(),configurable:true,writable:true});}catch(e){}});
}catch(e){}})();`;
