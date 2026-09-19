  // V2 display contract: finite numbers only; browser locale for raw/auto/K.
  // Explicit M and percentage retain the existing fixed-decimal presentation.
  function token(value) {
    if (!Number.isFinite(value)) return '-';
    const magnitude = Math.abs(value);
    let scale = 1, suffix = '', options = {};
    switch (unitMode()) {
      case 'm':
        return (value / 1e6).toFixed(magnitude < 1e7 ? 2 : 1) + 'M';
      case 'k': {
        scale = 1e3;
        suffix = 'K';
        const precision = magnitude < 1e5 ? 2 : magnitude < 1e6 ? 1 : 0;
        options = {minimumFractionDigits: precision, maximumFractionDigits: precision};
        break;
      }
      case 'auto':
        if (magnitude >= 1e6) { scale = 1e6; suffix = 'M'; }
        else if (magnitude >= 1e3) { scale = 1e3; suffix = 'K'; }
        options = {maximumFractionDigits: suffix ? 1 : 0};
        break;
    }
    return new Intl.NumberFormat(undefined, options).format(value / scale) + suffix;
  }

  function pct(value) {
    return Number.isFinite(value) ? value.toFixed(1) + '%' : '-';
  }
