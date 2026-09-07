(() => {
  const gameFields = document.querySelector('[data-game-fields]');
  const activityCheckboxes = document.querySelectorAll('input[name="activities"]');
  const ageField = document.querySelector('[data-child-age]');
  const ageRadios = document.querySelectorAll('input[name="participant_type"]');
  const ageInput = ageField?.querySelector('input');
  const childrenField = document.querySelector('[data-children-details]');
  const companionRadios = document.querySelectorAll('input[name="companions"]');
  const childrenInput = childrenField?.querySelector('input');

  const activity = (value) =>
    document.querySelector(`input[name="activities"][value="${value}"]`);

  const syncAge = () => {
    const selected = document.querySelector('input[name="participant_type"]:checked');
    const isChild = selected?.value === 'child';
    ageField.hidden = !isChild;
    ageInput.disabled = !isChild;
    ageInput.required = isChild;
    if (!isChild) ageInput.value = '';
  };

  const syncActivities = (changed) => {
    const game = activity('game');
    const supporter = activity('supporter');

    if (game?.checked && supporter?.checked) {
      if (changed?.value === 'supporter') game.checked = false;
      else supporter.checked = false;
    }

    const isGame = Boolean(game?.checked);
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
  activityCheckboxes.forEach((checkbox) =>
    checkbox.addEventListener('change', () => syncActivities(checkbox))
  );
  companionRadios.forEach((radio) => radio.addEventListener('change', syncChildren));
  syncActivities();
  syncChildren();
})();
