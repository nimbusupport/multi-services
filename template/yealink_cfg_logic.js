const FILE_HEADER = "#!version:1.0.0.1";
const DOMAIN_SUFFIX = ".nimbusip.com";
const OUTBOUND_PROXY = "213.57.30.66";
const DSS_KEY_START = 2;

const STATIC_LINES = [
  "dm.file_upload.http_method = 1",
  "dm.file_upload.http_post_mode = 0",
  "features.pickup.direct_pickup_code = **",
  "features.pickup.direct_pickup_enable = 1",
  "features.pickup.group_pickup_code = *8",
  "features.pickup.group_pickup_enable = 1",
  "lang.gui = Hebrew",
  "local_time.ntp_server1 = time.cloudflare.com",
  "local_time.ntp_server2 = il.pool.ntp.org",
  "local_time.time_zone = +2",
  "local_time.time_zone_name = Israel(Tel Aviv)",
  "phone_setting.backlight_time = 0",
  "syslog.dm.enable = 0",
  "transfer.dsskey_deal_type = 1",
  "voice.handfree.spk_vol = 14",
  "security.user_password = admin:N2mbusIP",
  "security.user_password = user:N1mbusIP",
  "static.auto_provision.server.url = https://eu-resource.ymcs.yealink.com/hardware/autop/$MAC.boot",
  "static.auto_provision.server.username = admin",
];

function cleanText(value) {
  return String(value ?? "").trim();
}

export function normalizeDomainPrefix(value) {
  return cleanText(value).replace(/\.nimbusip\.com$/i, "");
}

export function buildDomain(value) {
  const digits = normalizeDomainPrefix(value);
  return digits ? `${digits}${DOMAIN_SUFFIX}` : "";
}

function buildAccountLines(index, extension, password, domain) {
  return [
    `account.${index}.password = ${password}`,
    `account.${index}.auth_name = ${extension}`,
    `account.${index}.codec.pcmu.enable = 0`,
    `account.${index}.codec.pcma.priority = 1`,
    `account.${index}.codec.g729.enable = 0`,
    `account.${index}.codec.g722.enable = 0`,
    `account.${index}.display_name = ${extension}`,
    `account.${index}.enable = 1`,
    `account.${index}.label = ${extension}`,
    `account.${index}.outbound_proxy.1.address = ${OUTBOUND_PROXY}`,
    `account.${index}.outbound_proxy_enable = 1`,
    `account.${index}.sip_server.1.address = ${domain}`,
    `account.${index}.sip_server.1.expires = 600`,
    `account.${index}.user_name = ${extension}`,
  ];
}

function buildDssKeyLines(dssKeys) {
  return dssKeys.flatMap((entry, index) => {
    const keyIndex = DSS_KEY_START + index;
    const value = cleanText(entry.value);
    const label = cleanText(entry.label) || value;
    const line = cleanText(entry.line) || "1";
    const extension = cleanText(entry.extension) || "**";
    return [
      `linekey.${keyIndex}.extension = ${extension}`,
      `linekey.${keyIndex}.label = ${label}`,
      `linekey.${keyIndex}.line = ${line}`,
      `linekey.${keyIndex}.type = 16`,
      `linekey.${keyIndex}.value = ${value}`,
    ];
  });
}

function hasDssContent(entry) {
  const value = cleanText(entry?.value);
  const label = cleanText(entry?.label);
  const line = cleanText(entry?.line);
  const extension = cleanText(entry?.extension);
  return Boolean(
    value ||
    label ||
    (line && line !== "1") ||
    (extension && extension !== "**"),
  );
}

function hasAdditionalAccountContent(account) {
  return Boolean(cleanText(account?.extension) || cleanText(account?.password));
}

function withHeader(sections) {
  const body = sections
    .filter((section) => Array.isArray(section) && section.length > 0)
    .map((section) => section.join("\n"))
    .join("\n\n");
  return `${FILE_HEADER}\n\n${body}\n`;
}

export function buildTemplateConfig() {
  return withHeader([STATIC_LINES]);
}

export function validateConfigInput(state) {
  const errors = [];
  const domainPrefix = normalizeDomainPrefix(state.domainPrefix);
  const extension = cleanText(state.extension);
  const password = cleanText(state.password);
  const dssKeys = (state.dssKeys || []).filter(hasDssContent);
  const additionalAccounts = (state.additionalAccounts || []).filter(hasAdditionalAccountContent);

  if (!domainPrefix) {
    errors.push("Domain is required.");
  } else if (!/^\d+$/.test(domainPrefix)) {
    errors.push("Domain must contain numbers only.");
  }

  if (!extension) {
    errors.push("Extension is required.");
  }

  if (!password) {
    errors.push("Password is required.");
  }

  if (state.isW70B) {
    additionalAccounts.forEach((account, index) => {
      if (!cleanText(account.extension)) {
        errors.push(`W70B account ${index + 2} needs an extension.`);
      }
    });
  } else {
    dssKeys.forEach((entry, index) => {
      if (!cleanText(entry.value)) {
        errors.push(`Dsskey row ${index + 1} needs a BLF extension value.`);
      }
    });
  }

  return {
    errors,
    normalized: {
      domainPrefix,
      domain: buildDomain(domainPrefix),
      extension,
      password,
      isW70B: Boolean(state.isW70B),
      dssKeys: dssKeys.map((entry) => ({
        value: cleanText(entry.value),
        label: cleanText(entry.label),
        line: cleanText(entry.line) || "1",
        extension: cleanText(entry.extension) || "**",
      })),
      additionalAccounts: additionalAccounts.map((account) => ({
        extension: cleanText(account.extension),
        password: cleanText(account.password),
      })),
    },
  };
}

export function buildGeneratedConfig(state) {
  const { errors, normalized } = validateConfigInput(state);
  if (errors.length) {
    return { errors, content: "" };
  }

  const accountLines = normalized.isW70B
    ? [
        buildAccountLines(1, normalized.extension, normalized.password, normalized.domain),
        ...normalized.additionalAccounts.map((account, index) =>
          buildAccountLines(
            index + 2,
            account.extension,
            account.password || normalized.password,
            normalized.domain,
          ),
        ),
      ]
    : [buildAccountLines(1, normalized.extension, normalized.password, normalized.domain)];

  const sections = [STATIC_LINES, ...accountLines];
  if (!normalized.isW70B && normalized.dssKeys.length) {
    sections.push(buildDssKeyLines(normalized.dssKeys));
  }

  return {
    errors: [],
    content: withHeader(sections),
  };
}

export function createDownloadName(state) {
  const extension = cleanText(state.extension) || "yealink";
  const mode = state.isW70B ? "w70b" : "desk";
  return `${extension}-${mode}.cfg`;
}
