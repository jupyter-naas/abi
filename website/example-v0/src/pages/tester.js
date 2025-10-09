import React from 'react';
import Layout from '@theme/Layout';
import { useState, useEffect } from 'react';

// Import the working chat interface
import ChatInterface from '../components/Chat';

const ABI_API_BASE = 'http://localhost:9879';

export default function Tester() {
  const [instances, setInstances] = useState([]);
  const [selectedInstance, setSelectedInstance] = useState(null);

  useEffect(() => {
    fetchInstances();
  }, []);

  const fetchInstances = async () => {
    try {
      const response = await fetch(`${ABI_API_BASE}/web-platform/instances`);
      if (response.ok) {
        const data = await response.json();
        setInstances(data);
      }
    } catch (error) {
      console.error('Failed to fetch instances:', error);
    }
  };

  const deployInstance = async (instanceId) => {
    try {
      const response = await fetch(`${ABI_API_BASE}/web-platform/instances/${instanceId}/deploy`, {
        method: 'POST'
      });
      
      if (response.ok) {
        const result = await response.json();
        alert(`Instance deployed successfully!\nConfig: ${result.config_file}\nAPI: ${result.api_endpoint}`);
        fetchInstances();
      } else {
        alert('Failed to deploy instance');
      }
    } catch (error) {
      alert(`Failed to deploy instance: ${error}`);
    }
  };

  return (
    <Layout
      title="AI Tester"
      description="Test your custom AI instances with a chat interface">
      
      <div className="container margin-vert--lg">
        <div className="row">
          <div className="col col--4">
            <h1>AI Instances</h1>
            <button 
              className="button button--outline button--sm margin-bottom--md"
              onClick={fetchInstances}
            >
              Refresh
            </button>
            
            <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
              {instances.length === 0 ? (
                <div className="card">
                  <div className="card__body" style={{ textAlign: 'center' }}>
                    <p>No AI instances found.</p>
                    <a href="/builder" className="button button--primary">
                      Create Your First AI
                    </a>
                  </div>
                </div>
              ) : (
                instances.map((instance) => (
                  <div
                    key={instance.id}
                    className={`card margin-bottom--md ${
                      selectedInstance?.id === instance.id ? 'card--selected' : ''
                    }`}
                    style={{ 
                      cursor: 'pointer',
                      border: selectedInstance?.id === instance.id 
                        ? '2px solid var(--ifm-color-primary)' 
                        : '1px solid var(--ifm-color-emphasis-300)'
                    }}
                    onClick={() => setSelectedInstance(instance)}
                  >
                    <div className="card__body">
                      <h4>{instance.name}</h4>
                      <p style={{ fontSize: '0.9em', marginBottom: '8px' }}>
                        {instance.config.description}
                      </p>
                      
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span className={`badge ${
                          instance.status === 'running' ? 'badge--success' :
                          instance.status === 'deployed' ? 'badge--info' :
                          instance.status === 'draft' ? 'badge--secondary' : 
                          'badge--danger'
                        }`}>
                          {instance.status}
                        </span>
                        
                        {instance.status === 'draft' && (
                          <button
                            className="button button--primary button--sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              deployInstance(instance.id);
                            }}
                          >
                            Deploy
                          </button>
                        )}
                      </div>
                      
                      <div style={{ marginTop: '8px', fontSize: '0.8em' }}>
                        <div>
                          Models: {instance.config.modules.ai_models.length} |
                          Experts: {instance.config.modules.domain_experts.length} |
                          Apps: {instance.config.modules.applications.length}
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="col col--8">
            <div className="card" style={{ height: '80vh' }}>
              <div className="card__header">
                <h2>
                  {selectedInstance ? `Testing: ${selectedInstance.name}` : 'AI Chat Interface'}
                </h2>
                <p>
                  {selectedInstance 
                    ? selectedInstance.config.description 
                    : 'Select an AI instance to start testing'
                  }
                </p>
              </div>
              <div className="card__body" style={{ height: 'calc(100% - 120px)' }}>
                <ChatInterface />
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
