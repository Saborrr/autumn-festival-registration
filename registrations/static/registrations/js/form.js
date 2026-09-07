(() => {
  const gameFields = document.querySelector('[data-game-fields]');
  const formatRadios = document.querySelectorAll('input[name="participation_format"]');
  const ageField = document.querySelector('[data-child-age]');
  const ageRadios = document.querySelectorAll('input[name="participant_type"]');
  const ageInput = ageField?.querySelector('input');
  const childrenField = document.querySelector('[data-children-details]');
  const companionRadios = document.querySelectorAll('input[name="companions"]');
  const childrenInput = childrenField?.querySelector('input');

  const syncAge = () => {
    const selected = document.querySelector('input[name="participant_type"]:checked');
    const isChild = selected?.value === 'child';
    ageField.hidden = !isChild;
    ageInput.disabled = !isChild;
    ageInput.required = isChild;
    if (!isChild) ageInput.value = '';
  };
  const syncFormat = () => {
    const selected = document.querySelector('input[name="participation_format"]:checked');
    const isGame = selected?.value === 'game';
    gameFields.hidden = !isGame;
    gameFields.querySelectorAll('select,input').forEach((field) => {
      field.disabled = !isGame;
    });
    if (isGame) syncAge();
  };
  const syncChildren = () => {
    const selected = document.querySelector('input[name="companions"]:checked');
    const hasChildren = selected?.value === 'children';
    childrenField.hidden = !hasChildren;
    childrenInput.disabled = !hasChildren;
    childrenInput.required = hasChildren;
    if (!hasChildren) childrenInput.value = '';
  };
  ageRadios.forEach((radio) => radio.addEventListener('change', syncAge));
  formatRadios.forEach((radio) => radio.addEventListener('change', syncFormat));
  companionRadios.forEach((radio) => radio.addEventListener('change', syncChildren));
  syncFormat();
  syncChildren();
})();
