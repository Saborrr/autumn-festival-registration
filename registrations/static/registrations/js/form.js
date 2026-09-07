(() => {
  const ageField = document.querySelector('[data-child-age]');
  const radios = document.querySelectorAll('input[name="participant_type"]');
  if (!ageField || !radios.length) return;
  const input = ageField.querySelector('input');
  const sync = () => {
    const selected = document.querySelector('input[name="participant_type"]:checked');
    const isChild = selected?.value === 'child';
    ageField.hidden = !isChild;
    input.disabled = !isChild;
    input.required = isChild;
    if (!isChild) input.value = '';
  };
  radios.forEach((radio) => radio.addEventListener('change', sync));
  sync();
})();
