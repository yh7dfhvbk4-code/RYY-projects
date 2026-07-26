
/* ========== 全局JS ========== */

// 导航栏滚动效果
$(window).scroll(function() {
  if ($(this).scrollTop() > 50) {
    $('.navbar-custom').addClass('scrolled');
  } else {
    $('.navbar-custom').removeClass('scrolled');
  }
});

// 导航栏当前页面高亮
$(document).ready(function() {
  var currentPage = window.location.pathname.split('/').pop() || 'index.html';
  $('.navbar-nav .nav-link').each(function() {
    var href = $(this).attr('href');
    if (href === currentPage) {
      $(this).addClass('active');
    }
  });

  // 移动端导航点击后自动收起
  $('.navbar-nav .nav-link').on('click', function() {
    $('.navbar-collapse').collapse('hide');
  });
});

// 滚动动画 - 元素进入视口时添加动画
function initScrollAnimations() {
  var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate-in');
      }
    });
  }, { threshold: 0.15 });

  document.querySelectorAll('.animate-on-scroll').forEach(function(el) {
    observer.observe(el);
  });
}

// 初始化计数器动画
function initCounters() {
  var counters = document.querySelectorAll('.counter');
  counters.forEach(function(counter, index) {
    setTimeout(function() {
      animateCounter(counter);
    }, index * 200);
  });
}

// 数字计数动画
function animateCounter(el) {
  var target = parseInt(el.getAttribute('data-target'));
  var suffix = el.getAttribute('data-suffix') || '';
  var duration = 2000;
  var start = 0;
  var startTime = null;

  function step(timestamp) {
    if (!startTime) startTime = timestamp;
    var progress = Math.min((timestamp - startTime) / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
    var current = Math.floor(eased * target);
    el.textContent = current.toLocaleString() + suffix;
    if (progress < 1) {
      requestAnimationFrame(step);
    }
  }
  requestAnimationFrame(step);
}

// 粒子动画
function initParticles(canvasId) {
  var canvas = document.getElementById(canvasId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  var particles = [];
  var maxParticles = 80;

  function resize() {
    canvas.width = canvas.parentElement.offsetWidth;
    canvas.height = canvas.parentElement.offsetHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  function Particle() {
    this.x = Math.random() * canvas.width;
    this.y = Math.random() * canvas.height;
    this.vx = (Math.random() - 0.5) * 0.8;
    this.vy = (Math.random() - 0.5) * 0.8;
    this.radius = Math.random() * 2 + 1;
    this.opacity = Math.random() * 0.5 + 0.2;
  }

  for (var i = 0; i < maxParticles; i++) {
    particles.push(new Particle());
  }

  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    particles.forEach(function(p, idx) {
      p.x += p.vx;
      p.y += p.vy;

      if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(108, 92, 231, ' + p.opacity + ')';
      ctx.fill();

      // 连线
      for (var j = idx + 1; j < particles.length; j++) {
        var dx = p.x - particles[j].x;
        var dy = p.y - particles[j].y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 150) {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = 'rgba(108, 92, 231, ' + (0.15 * (1 - dist / 150)) + ')';
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    });

    requestAnimationFrame(draw);
  }
  draw();
}

// 打字机效果
function initTypewriter(elementId, texts, speed) {
  var el = document.getElementById(elementId);
  if (!el) return;
  var textIndex = 0;
  var charIndex = 0;
  var isDeleting = false;
  speed = speed || 80;

  function type() {
    var currentText = texts[textIndex];
    if (isDeleting) {
      el.textContent = currentText.substring(0, charIndex - 1);
      charIndex--;
    } else {
      el.textContent = currentText.substring(0, charIndex + 1);
      charIndex++;
    }

    var delay = speed;
    if (isDeleting) delay = speed / 2;
    if (!isDeleting && charIndex === currentText.length) {
      delay = 2000;
      isDeleting = true;
    } else if (isDeleting && charIndex === 0) {
      isDeleting = false;
      textIndex = (textIndex + 1) % texts.length;
      delay = 500;
    }
    setTimeout(type, delay);
  }
  type();
}

// 表单验证
function initFormValidation(formId) {
  var form = document.getElementById(formId);
  if (!form) return;

  // 实时验证
  $(form).find('input, textarea, select').on('input blur', function() {
    validateField(this);
  });

  $(form).on('submit', function(e) {
    e.preventDefault();
    var isValid = true;
    $(this).find('input, textarea, select').each(function() {
      if (!validateField(this)) {
        isValid = false;
      }
    });
    if (isValid) {
      showSubmitSuccess(form);
    }
  });
}

function validateField(field) {
  var $field = $(field);
  var value = $field.val().trim();
  var type = $field.attr('type');
  var required = $field.prop('required');
  var isValid = true;
  var errorMsg = '';

  // 清除旧状态
  $field.removeClass('is-valid is-invalid');
  $field.siblings('.invalid-feedback').remove();

  if (required && !value) {
    isValid = false;
    errorMsg = '此字段为必填项';
  } else if (value) {
    if (type === 'email') {
      var emailReg = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailReg.test(value)) {
        isValid = false;
        errorMsg = '请输入有效的邮箱地址';
      }
    } else if (type === 'tel') {
      var telReg = /^1[3-9]\d{9}$/;
      if (!telReg.test(value)) {
        isValid = false;
        errorMsg = '请输入有效的手机号码';
      }
    } else if ($field.attr('minlength') && value.length < parseInt($field.attr('minlength'))) {
      isValid = false;
      errorMsg = '最少输入' + $field.attr('minlength') + '个字符';
    }
  }

  if (isValid) {
    $field.addClass('is-valid');
  } else {
    $field.addClass('is-invalid');
    $field.after('<div class="invalid-feedback">' + errorMsg + '</div>');
  }
  return isValid;
}

function showSubmitSuccess(form) {
  var $btn = $(form).find('button[type="submit"]');
  var originalText = $btn.html();
  $btn.html('<i class="fas fa-check me-2"></i>提交成功！').prop('disabled', true).removeClass('btn-glow-primary').addClass('btn-success');

  // 显示成功提示
  var alertHtml = '<div class="alert alert-success mt-3 animate-on-scroll animate-in" role="alert"><i class="fas fa-check-circle me-2"></i>感谢您的留言！我们会尽快与您联系。</div>';
  $(form).find('.form-success-area').html(alertHtml);

  setTimeout(function() {
    form.reset();
    $(form).find('.is-valid, .is-invalid').removeClass('is-valid is-invalid');
    $(form).find('.invalid-feedback').remove();
    $btn.html(originalText).prop('disabled', false).removeClass('btn-success').addClass('btn-glow-primary');
    $(form).find('.form-success-area').empty();
  }, 4000);
}

// Tab内容切换
function initTabs(tabContainerId) {
  var $container = $('#' + tabContainerId);
  if (!$container.length) return;

  $container.find('.tab-btn').on('click', function() {
    var target = $(this).data('tab');

    // 切换按钮样式
    $container.find('.tab-btn').removeClass('btn-glow-primary').addClass('btn-glow-outline');
    $(this).removeClass('btn-glow-outline').addClass('btn-glow-primary');

    // 切换内容面板
    $container.find('.tab-pane').removeClass('show').hide();
    $container.find('#' + target).addClass('show').fadeIn(400);
  });
}

// 初始化
$(document).ready(function() {
  initScrollAnimations();
  
  // 页面加载后延迟启动计数器动画
  setTimeout(function() {
    initCounters();
  }, 500);
});
