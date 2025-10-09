import React from 'react';
import styles from './styles.module.css';

export default function ScheduleSection() {
  return (
    <div className={styles.schedulePage}>
      <div className="container">
        <div className={styles.scheduleHeader}>
          <h1>Schedule an Executive Briefing</h1>
          <p>Experience how BOB can transform your enterprise with a personalized demonstration.</p>
        </div>

        <div className={styles.scheduleGrid}>
          <div className={styles.scheduleForm}>
            <h2>Book Your Session</h2>
            <form>
              <div className={styles.formGroup}>
                <label htmlFor="name">Full Name</label>
                <input type="text" id="name" name="name" required />
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="title">Job Title</label>
                <input type="text" id="title" name="title" required />
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="company">Company</label>
                <input type="text" id="company" name="company" required />
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="email">Business Email</label>
                <input type="email" id="email" name="email" required />
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="phone">Phone Number</label>
                <input type="tel" id="phone" name="phone" required />
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="country">Country</label>
                <select id="country" name="country" required>
                  <option value="">Select your country</option>
                  <option value="US">United States</option>
                  <option value="UK">United Kingdom</option>
                  <option value="FR">France</option>
                  <option value="DE">Germany</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="industry">Industry</label>
                <select id="industry" name="industry" required>
                  <option value="">Select your industry</option>
                  <option value="financial">Financial Services</option>
                  <option value="technology">Technology</option>
                  <option value="healthcare">Healthcare</option>
                  <option value="manufacturing">Manufacturing</option>
                  <option value="retail">Retail</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="interests">Areas of Interest</label>
                <div className={styles.checkboxGroup}>
                  <label>
                    <input type="checkbox" name="interests" value="market-intelligence" />
                    Market Intelligence
                  </label>
                  <label>
                    <input type="checkbox" name="interests" value="capability-mapping" />
                    Capability Mapping
                  </label>
                  <label>
                    <input type="checkbox" name="interests" value="governance" />
                    Human-in-the-Loop Governance
                  </label>
                </div>
              </div>

              <div className={styles.formGroup}>
                <label htmlFor="message">Additional Information</label>
                <textarea
                  id="message"
                  name="message"
                  rows="4"
                  placeholder="Tell us about your specific needs or challenges"></textarea>
              </div>

              <button type="submit" className="button button--primary button--lg">
                Schedule Demo
              </button>
            </form>
          </div>

          <div className={styles.scheduleInfo}>
            <div className={styles.infoCard}>
              <h3>What to Expect</h3>
              <ul>
                <li>60-minute personalized demonstration</li>
                <li>Q&A session with our experts</li>
                <li>Custom solution discussion</li>
                <li>Implementation roadmap</li>
              </ul>
            </div>

            <div className={styles.infoCard}>
              <h3>Why Schedule a Demo?</h3>
              <ul>
                <li>See BOB's capabilities in action</li>
                <li>Discuss your specific use cases</li>
                <li>Learn about implementation options</li>
                <li>Get pricing information</li>
              </ul>
            </div>

            <div className={styles.infoCard}>
              <h3>Who Should Attend?</h3>
              <ul>
                <li>C-Level Executives</li>
                <li>Digital Transformation Leaders</li>
                <li>Risk & Compliance Officers</li>
                <li>Technology Decision Makers</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 