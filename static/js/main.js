// Основные функции JavaScript
document.addEventListener('DOMContentLoaded', function() {
  // Инициализация tooltips
  initTooltips();
  
  // Инициализация прогресс-баров
  initProgressBars();
  
  // Анимации при скролле
  initScrollAnimations();
});

function initTooltips() {
  const tooltips = document.querySelectorAll('[data-tooltip]');
  
  tooltips.forEach(tooltip => {
      tooltip.addEventListener('mouseenter', showTooltip);
      tooltip.addEventListener('mouseleave', hideTooltip);
  });
}

function showTooltip(e) {
  const tooltipText = this.getAttribute('data-tooltip');
  const tooltip = document.createElement('div');
  tooltip.className = 'tooltip';
  tooltip.textContent = tooltipText;
  
  document.body.appendChild(tooltip);
  
  const rect = this.getBoundingClientRect();
  tooltip.style.left = rect.left + (rect.width - tooltip.offsetWidth) / 2 + 'px';
  tooltip.style.top = rect.top - tooltip.offsetHeight - 5 + 'px';
}

function hideTooltip() {
  const tooltip = document.querySelector('.tooltip');
  if (tooltip) {
      tooltip.remove();
  }
}

function initProgressBars() {
  const progressBars = document.querySelectorAll('.progress-fill');
  
  progressBars.forEach(bar => {
      const progress = bar.getAttribute('data-progress') || 0;
      bar.style.width = progress + '%';
  });
}

function initScrollAnimations() {
  const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
          if (entry.isIntersecting) {
              entry.target.classList.add('animate-in');
          }
      });
  }, { threshold: 0.1 });
  
  document.querySelectorAll('.lesson-card, .card').forEach(el => {
      observer.observe(el);
  });
}

// Утилиты
function formatXP(xp) {
  return xp.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.className = `notification notification-${type}`;
  notification.textContent = message;
  
  document.body.appendChild(notification);
  
  setTimeout(() => {
      notification.classList.add('show');
  }, 100);
  
  setTimeout(() => {
      notification.classList.remove('show');
      setTimeout(() => {
          notification.remove();
      }, 300);
  }, 3000);
}

// CSS для уведомлений и тултипов
const style = document.createElement('style');
style.textContent = `
  .tooltip {
      position: fixed;
      background: rgba(0,0,0,0.8);
      color: white;
      padding: 0.5rem 1rem;
      border-radius: 4px;
      font-size: 0.875rem;
      z-index: 10000;
      pointer-events: none;
  }
  
  .notification {
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 1rem 1.5rem;
      border-radius: 8px;
      color: white;
      transform: translateX(400px);
      transition: transform 0.3s ease;
      z-index: 10000;
  }
  
  .notification.show {
      transform: translateX(0);
  }
  
  .notification-info {
      background: var(--secondary-color);
  }
  
  .notification-success {
      background: var(--primary-color);
  }
  
  .notification-error {
      background: var(--accent-color);
  }
  
  .animate-in {
      animation: fadeInUp 0.6s ease;
  }
  
  @keyframes fadeInUp {
      from {
          opacity: 0;
          transform: translateY(30px);
      }
      to {
          opacity: 1;
          transform: translateY(0);
      }
  }
`;
document.head.appendChild(style);
