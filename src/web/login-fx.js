// Decorative motion for the login hero panel: pointer parallax and rotating examples.
(() => {
  const hero = document.querySelector('.auth-hero');
  if (!hero || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  // Pointer parallax: layers with data-depth drift toward the cursor.
  const layers = [...hero.querySelectorAll('[data-depth]')];
  let frame = 0;
  hero.addEventListener('pointermove', event => {
    const rect = hero.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - .5;
    const y = (event.clientY - rect.top) / rect.height - .5;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      hero.style.setProperty('--px', x.toFixed(3));
      hero.style.setProperty('--py', y.toFixed(3));
      layers.forEach(layer => {
        const depth = Number(layer.dataset.depth) || 1;
        layer.style.transform = `translate3d(${x * depth * 14}px, ${y * depth * 14}px, 0) rotateX(${-y * 6}deg) rotateY(${x * 8}deg)`;
      });
    });
  });
  hero.addEventListener('pointerleave', () => {
    layers.forEach(layer => { layer.style.transform = ''; });
  });

  // Rotating Q&A examples in the student chat mock.
  const question = hero.querySelector('[data-rotate-q]');
  const answer = hero.querySelector('[data-rotate-a]');
  const source = hero.querySelector('[data-rotate-s]');
  if (!question || !answer) return;
  const examples = [
    ['Học phí IT1 là bao nhiêu?', 'Khoảng <b>28–40 triệu đồng/năm</b> với chương trình chuẩn.', 'Nguồn · PDF trang 20 ↗'],
    ['Đăng ký thi đánh giá tư duy thế nào?', 'Mình có <b>checklist từng bước</b> và dẫn trang PDF để bạn đối chiếu.', 'Checklist đăng ký ĐGTD ↗'],
    ['Em chưa biết nên chọn ngành nào?', 'Thử <b>Gợi ý ngành</b> theo thế mạnh và sở thích của bạn nhé.', 'Gợi ý ngành tham khảo ↗'],
  ];
  const chat = question.closest('.auth-chat');
  let index = 0;
  setInterval(() => {
    if (document.hidden) return;
    chat.classList.add('is-swapping');
    setTimeout(() => {
      index = (index + 1) % examples.length;
      const [q, a, s] = examples[index];
      question.textContent = q;
      answer.innerHTML = a;
      if (source) source.textContent = s;
      chat.classList.remove('is-swapping');
    }, 450);
  }, 4200);
})();
