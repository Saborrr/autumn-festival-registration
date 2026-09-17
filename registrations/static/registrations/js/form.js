(() => {
  const gameFields = document.querySelector('[data-game-fields]');
  const activityCheckboxes = document.querySelectorAll('input[name="activities"]');
  const ageField = document.querySelector('[data-child-age]');
  const ageRadios = document.querySelectorAll('input[name="participant_type"]');
  const ageInput = ageField?.querySelector('input');
  const childrenField = document.querySelector('[data-companion-children]');
  const childRows = childrenField?.querySelector('[data-child-rows]');
  const addChildButton = childrenField?.querySelector('[data-add-child]');
  const maxChildren = Number(childRows?.dataset.maxChildren || 10);
  const companionCheckboxes = document.querySelectorAll('input[name="companions"]');

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

  const companion = (value) =>
    document.querySelector(`input[name="companions"][value="${value}"]`);

  const syncAddChildAvailability = () => {
    if (!addChildButton) return;
    const hasChildren = Boolean(companion('children')?.checked);
    const atLimit = childRows.querySelectorAll('[data-child-row]').length >= maxChildren;
    addChildButton.disabled = !hasChildren || atLimit;
    addChildButton.setAttribute('aria-disabled', String(!hasChildren || atLimit));
  };

  const renumberChildren = () => {
    childRows?.querySelectorAll('[data-child-row]').forEach((row, index) => {
      const number = index + 1;
      const label = row.querySelector('label');
      const input = row.querySelector('input');
      const remove = row.querySelector('[data-remove-child]');
      input.id = `id_child_ages_${index}`;
      input.setAttribute('aria-label', `Возраст ребёнка ${number}`);
      label.htmlFor = input.id;
      label.textContent = `Ребёнок ${number}`;
      remove.setAttribute('aria-label', `Удалить ребёнка ${number}`);
    });
    syncAddChildAvailability();
  };

  const addChildRow = (value = '') => {
    if (!childRows || childRows.querySelectorAll('[data-child-row]').length >= maxChildren) return;
    const row = document.createElement('div');
    row.className = 'child-age-row';
    row.dataset.childRow = '';
    const label = document.createElement('label');
    const controls = document.createElement('div');
    const input = document.createElement('input');
    const remove = document.createElement('button');
    controls.className = 'child-age-controls';
    input.type = 'number';
    input.name = 'child_ages';
    input.min = '0';
    input.max = '17';
    input.inputMode = 'numeric';
    input.value = value;
    remove.type = 'button';
    remove.className = 'remove-child';
    remove.dataset.removeChild = '';
    remove.textContent = 'Удалить';
    controls.append(input, remove);
    row.append(label, controls);
    childRows.appendChild(row);
    renumberChildren();
    input.focus();
  };

  const syncCompanions = (changed) => {
    const alone = companion('alone');
    const adult = companion('adult_relative');
    const children = companion('children');

    if (changed?.checked && changed.value === 'alone') {
      if (adult) adult.checked = false;
      if (children) children.checked = false;
    } else if (changed?.checked && (changed.value === 'adult_relative' || changed.value === 'children')) {
      if (alone) alone.checked = false;
    }

    const hasChildren = Boolean(children?.checked);
    childrenField.hidden = !hasChildren;
    childrenField.querySelectorAll('input,button').forEach((field) => {
      field.disabled = !hasChildren;
    });
    const inputs = childRows.querySelectorAll('input[name="child_ages"]');
    inputs.forEach((input) => { input.required = hasChildren; });
    if (!hasChildren) inputs.forEach((input) => { input.value = ''; });
    syncAddChildAvailability();
  };

  childRows?.addEventListener('click', (event) => {
    const button = event.target.closest('[data-remove-child]');
    if (!button) return;
    button.closest('[data-child-row]').remove();
    if (!childRows.querySelector('[data-child-row]')) addChildRow();
    renumberChildren();
  });
  addChildButton?.addEventListener('click', () => addChildRow());
  ageRadios.forEach((radio) => radio.addEventListener('change', syncAge));
  activityCheckboxes.forEach((checkbox) =>
    checkbox.addEventListener('change', () => syncActivities(checkbox))
  );
  companionCheckboxes.forEach((checkbox) =>
    checkbox.addEventListener('change', () => syncCompanions(checkbox))
  );
  renumberChildren();
  syncActivities();
  syncCompanions();
})();
