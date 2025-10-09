import React from 'react';
import Layout from '@theme/Layout';
import { useState, useEffect } from 'react';

// Import the working chat interface from your proven pattern
import ChatInterface from '../components/Chat';

const ABI_API_BASE = 'http://localhost:9879';

export default function Builder() {
  const [modules, setModules] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedModules, setSelectedModules] = useState({
    'ai-models': [],
    'domain-experts': [],
    'applications': []
  });
  const [aiConfig, setAiConfig] = useState({
    name: '',
    description: '',
    deployment_type: 'personal'
  });

  useEffect(() => {
    fetchModules();
  }, []);

  const fetchModules = async () => {
    try {
      const response = await fetch(`${ABI_API_BASE}/web-platform/modules`);
      if (response.ok) {
        const data = await response.json();
        setModules(data);
      }
    } catch (error) {
      console.error('Failed to fetch modules:', error);
    } finally {
      setLoading(false);
    }
  };

  const createAIInstance = async () => {
    if (!aiConfig.name || !aiConfig.description) {
      alert('Please fill in name and description');
      return;
    }

    const config = {
      name: aiConfig.name,
      description: aiConfig.description,
      deployment_type: aiConfig.deployment_type,
      modules: {
        core_modules: [],
        domain_experts: selectedModules['domain-experts'],
        applications: selectedModules['applications'],
        ai_models: selectedModules['ai-models'],
      },
    };

    try {
      const response = await fetch(`${ABI_API_BASE}/web-platform/instances`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (response.ok) {
        const newInstance = await response.json();
        alert(`AI instance "${newInstance.name}" created successfully!`);
        
        // Reset form
        setAiConfig({ name: '', description: '', deployment_type: 'personal' });
        setSelectedModules({ 'ai-models': [], 'domain-experts': [], 'applications': [] });
      } else {
        alert('Failed to create AI instance');
      }
    } catch (error) {
      alert(`Failed to create AI instance: ${error}`);
    }
  };

  const handleModuleToggle = (moduleType, modulePath) => {
    setSelectedModules(prev => ({
      ...prev,
      [moduleType]: prev[moduleType].includes(modulePath)
        ? prev[moduleType].filter(path => path !== modulePath)
        : [...prev[moduleType], modulePath]
    }));
  };

  if (loading) {
    return (
      <Layout>
        <div className="container margin-vert--lg">
          <div style={{ textAlign: 'center' }}>Loading modules...</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout
      title="AI Builder"
      description="Build your custom AI by selecting modules and configuring capabilities">
      
      <div className="container margin-vert--lg">
        <div className="row">
          <div className="col col--8">
            <h1>AI Builder</h1>
            <p>Create your custom AI by selecting modules and configuring capabilities</p>
            
            {/* AI Configuration Form */}
            <div className="card margin-bottom--lg">
              <div className="card__header">
                <h3>AI Configuration</h3>
              </div>
              <div className="card__body">
                <div className="margin-bottom--md">
                  <label>AI Name</label>
                  <input
                    type="text"
                    className="form-control"
                    value={aiConfig.name}
                    onChange={(e) => setAiConfig(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="My Custom AI"
                    style={{ width: '100%', padding: '8px', marginTop: '4px' }}
                  />
                </div>
                <div className="margin-bottom--md">
                  <label>Description</label>
                  <textarea
                    className="form-control"
                    value={aiConfig.description}
                    onChange={(e) => setAiConfig(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe what your AI will do..."
                    rows={3}
                    style={{ width: '100%', padding: '8px', marginTop: '4px' }}
                  />
                </div>
                <div className="margin-bottom--md">
                  <label>Deployment Type</label>
                  <select
                    value={aiConfig.deployment_type}
                    onChange={(e) => setAiConfig(prev => ({ ...prev, deployment_type: e.target.value }))}
                    style={{ width: '100%', padding: '8px', marginTop: '4px' }}
                  >
                    <option value="personal">Personal</option>
                    <option value="hosted">Hosted</option>
                    <option value="embedded">Embedded</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Module Selection */}
            {modules && Object.entries(modules).map(([moduleType, moduleList]) => (
              <div key={moduleType} className="card margin-bottom--lg">
                <div className="card__header">
                  <h3 style={{ textTransform: 'capitalize' }}>
                    {moduleType.replace('-', ' ')} ({moduleList.length})
                  </h3>
                </div>
                <div className="card__body">
                  <div className="row">
                    {moduleList.map((module) => (
                      <div key={module.path} className="col col--6 margin-bottom--md">
                        <div 
                          className={`card ${selectedModules[moduleType]?.includes(module.path) ? 'card--selected' : ''}`}
                          style={{ 
                            cursor: 'pointer',
                            border: selectedModules[moduleType]?.includes(module.path) 
                              ? '2px solid var(--ifm-color-primary)' 
                              : '1px solid var(--ifm-color-emphasis-300)',
                            backgroundColor: selectedModules[moduleType]?.includes(module.path) 
                              ? 'var(--ifm-color-primary-lightest)' 
                              : 'inherit'
                          }}
                          onClick={() => handleModuleToggle(moduleType, module.path)}
                        >
                          <div className="card__body">
                            <h4>{module.name}</h4>
                            <p style={{ fontSize: '0.9em', color: 'var(--ifm-color-emphasis-700)' }}>
                              {module.description}
                            </p>
                            <span className="badge badge--secondary">{module.type}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}

            <div style={{ textAlign: 'center', marginTop: '2rem' }}>
              <button 
                className="button button--primary button--lg"
                onClick={createAIInstance}
              >
                Create AI Instance
              </button>
            </div>
          </div>

          {/* Chat Interface Sidebar */}
          <div className="col col--4">
            <div className="card">
              <div className="card__header">
                <h3>Test Your AI</h3>
                <p>Chat with ABI to test your configuration</p>
              </div>
              <div className="card__body" style={{ height: '600px' }}>
                <ChatInterface />
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
