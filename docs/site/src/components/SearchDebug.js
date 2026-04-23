import React from 'react';

export default function SearchDebug() {
 return (
 <div style={{
 position: 'fixed',
 top: '10px',
 right: '10px',
 background: 'red',
 color: 'white',
 padding: '10px',
 zIndex: 9999,
 fontSize: '12px'
 }}>
 <div>Search Debug Info:</div>
 <div>Algolia Config: {typeof window !== 'undefined' && window.docusaurus ? 'Found' : 'Missing'}</div>
 <div>Search Theme: {typeof window !== 'undefined' && window.DocusaurusSearchModal ? 'Loaded' : 'Not Loaded'}</div>
 </div>
 );
}
