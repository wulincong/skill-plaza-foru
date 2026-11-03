#!/usr/bin/env node

import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const skillRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const resourcesRoot = resolve(skillRoot, 'resources');
const registryPath = resolve(resourcesRoot, 'regions/registry.json');

const fail = (message) => {
  throw new Error(message);
};

const loadJson = async (path, label) => {
  try {
    return JSON.parse(await readFile(path, 'utf8'));
  } catch (error) {
    fail(`${label} is not valid JSON: ${error.message}`);
  }
};

const readSha256 = async (path, label) => {
  try {
    return createHash('sha256').update(await readFile(path)).digest('hex');
  } catch (error) {
    fail(`${label} cannot be hashed: ${error.message}`);
  }
};

const requireText = (value, label) => {
  if (typeof value !== 'string' || !value.trim()) fail(`${label} must be a non-empty string`);
  return value.trim();
};

const requireCode = (value, label) => {
  const code = String(value ?? '');
  if (!/^\d{6}$/.test(code)) fail(`${label} must be a six-digit code: ${code}`);
  return code;
};

const assertScope = (scope, expected, label) => {
  if (!scope || typeof scope !== 'object') fail(`${label}: scope must be an object`);
  if (scope.country !== expected.country) fail(`${label}: scope.country must be ${expected.country}`);
  if (scope.province !== expected.province) {
    fail(`${label}: scope.province must be ${expected.province}`);
  }
  if (String(scope.provinceCode ?? '') !== expected.provinceCode) {
    fail(`${label}: scope.provinceCode must be ${expected.provinceCode}`);
  }
  if (scope.level !== expected.level) fail(`${label}: scope.level must be ${expected.level}`);
};

const validateMapping = (mapping, expected, label) => {
  if (!mapping || typeof mapping !== 'object') fail(`${label}: mapping must be an object`);
  if (mapping.schemaVersion !== 1) fail(`${label}: schemaVersion must be 1`);
  assertScope(mapping.scope, expected, label);
  if (mapping.scope.codeSystem !== expected.codeSystem) {
    fail(`${label}: scope.codeSystem must be ${expected.codeSystem}`);
  }
  if (typeof mapping.boundaryResource !== 'string' || !mapping.boundaryResource.trim()) {
    fail(`${label}: boundaryResource must be a non-empty relative path`);
  }
  if (!Array.isArray(mapping.cities) || mapping.cities.length === 0) {
    fail(`${label}: cities must be a non-empty array`);
  }
  if (!mapping.cityNameToCode || typeof mapping.cityNameToCode !== 'object' || Array.isArray(mapping.cityNameToCode)) {
    fail(`${label}: cityNameToCode must be an object`);
  }

  const canonicalCodes = new Set();
  const namesByCode = new Map();
  const namesSeen = new Map();
  for (const city of mapping.cities) {
    if (!city || typeof city !== 'object') fail(`${label}: every city must be an object`);
    const code = requireCode(city.code, `${label}: city code`);
    const name = requireText(city.name, `${label}: city ${code} name`);
    if (canonicalCodes.has(code)) fail(`${label}: duplicate code ${code}`);
    canonicalCodes.add(code);
    namesByCode.set(code, name);

    const aliases = city.aliases ?? [];
    if (!Array.isArray(aliases)) fail(`${label}: aliases for ${code} must be an array`);
    for (const alias of [name, ...aliases]) {
      const normalized = requireText(alias, `${label}: alias for ${code}`);
      const previous = namesSeen.get(normalized);
      if (previous && previous !== code) {
        fail(`${label}: ambiguous name ${normalized} maps to ${previous} and ${code}`);
      }
      namesSeen.set(normalized, code);
    }
  }

  for (const [name, codeValue] of Object.entries(mapping.cityNameToCode)) {
    const code = requireCode(codeValue, `${label}: cityNameToCode ${name}`);
    if (!canonicalCodes.has(code)) fail(`${label}: cityNameToCode ${name} points to unknown code ${code}`);
    if (namesSeen.get(name) !== code) {
      fail(`${label}: cityNameToCode ${name} is missing from the city aliases for ${code}`);
    }
  }
  for (const [name, code] of namesSeen) {
    if (String(mapping.cityNameToCode[name] ?? '') !== code) {
      fail(`${label}: missing cityNameToCode mapping for ${name}`);
    }
  }

  return { canonicalCodes, namesByCode };
};

const validateBoundary = (boundaries, expected, mappingInfo, label) => {
  if (boundaries.type !== 'FeatureCollection' || !Array.isArray(boundaries.features)) {
    fail(`${label}: expected a GeoJSON FeatureCollection`);
  }
  const { canonicalCodes, namesByCode } = mappingInfo;
  if (boundaries.features.length !== canonicalCodes.size) {
    fail(`${label}: ${boundaries.features.length} features for ${canonicalCodes.size} mapped cities`);
  }
  const featureCodes = new Set();
  for (const feature of boundaries.features) {
    const properties = feature?.properties ?? {};
    const code = requireCode(properties.adcode, `${label}: boundary properties.adcode`);
    const name = requireText(properties.name, `${label}: boundary ${code} name`);
    if (featureCodes.has(code)) fail(`${label}: duplicate properties.adcode ${code}`);
    if (!canonicalCodes.has(code)) fail(`${label}: code ${code} is absent from city code mapping`);
    if (namesByCode.get(code) !== name) {
      fail(`${label}: ${code} name ${name} does not match ${namesByCode.get(code)}`);
    }
    if (properties.level !== 'city') fail(`${label}: ${code} must have level=city`);
    if (String(properties.parent?.adcode ?? '') !== expected.provinceCode) {
      fail(`${label}: ${code} must have parent.adcode=${expected.provinceCode}`);
    }
    if (!['MultiPolygon', 'Polygon'].includes(feature.geometry?.type)) {
      fail(`${label}: ${code} must use Polygon or MultiPolygon geometry`);
    }
    featureCodes.add(code);
  }
  for (const code of canonicalCodes) {
    if (!featureCodes.has(code)) fail(`${label}: missing feature for ${code}`);
  }
  return featureCodes;
};

const validateRegion = async (region, registryDir, registryDefaults) => {
  const province = requireText(region.province, 'registry region province');
  const provinceCode = requireCode(region.provinceCode, `registry ${province} provinceCode`);
  const id = requireText(region.id, `registry ${province} id`);
  const manifestRef = requireText(region.manifest, `registry ${province} manifest`);
  if (manifestRef.startsWith('/') || manifestRef.includes('..')) {
    fail(`registry ${province}: manifest must stay inside resources/regions: ${manifestRef}`);
  }
  const manifestPath = resolve(registryDir, manifestRef);
  const manifest = await loadJson(manifestPath, `${province} manifest`);
  if (manifest.schemaVersion !== 1) fail(`${province} manifest: schemaVersion must be 1`);
  if (manifest.resourceId !== id) fail(`${province} manifest: resourceId must be ${id}`);
  if (manifest.codeSystem !== registryDefaults.codeSystem) {
    fail(`${province} manifest: codeSystem must be ${registryDefaults.codeSystem}`);
  }
  const expected = {
    country: registryDefaults.country,
    province,
    provinceCode,
    level: registryDefaults.level,
    codeSystem: registryDefaults.codeSystem
  };
  assertScope(manifest.scope, expected, `${province} manifest`);
  const mappingRef = requireText(manifest.cityCodeMapping, `${province} manifest cityCodeMapping`);
  const boundaryRef = requireText(manifest.boundaryResource, `${province} manifest boundaryResource`);
  if (mappingRef.startsWith('/') || boundaryRef.startsWith('/')) {
    fail(`${province} manifest: resource paths must be relative`);
  }
  if (manifest.boundaryFormat !== 'geojson') {
    fail(`${province} manifest: boundaryFormat must be geojson`);
  }
  if (!manifest.source || typeof manifest.source !== 'object') {
    fail(`${province} manifest: source must be an object`);
  }
  const mappingPath = resolve(dirname(manifestPath), mappingRef);
  const boundaryPath = resolve(dirname(manifestPath), boundaryRef);
  const mapping = await loadJson(mappingPath, `${province} city code mapping`);
  const mappingInfo = validateMapping(mapping, expected, `${province} city code mapping`);
  const mappingBoundaryPath = resolve(dirname(mappingPath), mapping.boundaryResource);
  if (mappingBoundaryPath !== boundaryPath) {
    fail(`${province}: manifest boundaryResource and mapping boundaryResource resolve to different files`);
  }
  const boundaries = await loadJson(boundaryPath, `${province} boundary resource`);
  const featureCodes = validateBoundary(boundaries, expected, mappingInfo, `${province} boundary resource`);

  const declaredHash = String(manifest.source.sha256 ?? '').toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(declaredHash)) {
    fail(`${province} manifest: source.sha256 must be a 64-character hex digest`);
  }
  const actualHash = await readSha256(boundaryPath, `${province} boundary resource`);
  if (actualHash !== declaredHash) {
    fail(`${province} boundary resource: sha256 ${actualHash} does not match manifest ${declaredHash}`);
  }
  if (mapping.source?.sha256 && String(mapping.source.sha256).toLowerCase() !== actualHash) {
    fail(`${province} city code mapping: source.sha256 does not match boundary resource`);
  }

  return {
    id,
    province,
    provinceCode,
    cityCount: mappingInfo.canonicalCodes.size,
    aliasCount: Object.keys(mapping.cityNameToCode).length,
    boundaryCount: featureCodes.size,
    mappingPath,
    boundaryPath,
    manifestPath
  };
};

const registry = await loadJson(registryPath, 'region registry');
if (registry.schemaVersion !== 1) fail('region registry: schemaVersion must be 1');
const country = requireText(registry.country, 'region registry country');
const level = requireText(registry.level, 'region registry level');
const codeSystem = requireText(registry.codeSystem, 'region registry codeSystem');
if (!Array.isArray(registry.regions) || registry.regions.length === 0) {
  fail('region registry: regions must be a non-empty array');
}
if (!registry.provinceNameToCode || typeof registry.provinceNameToCode !== 'object' || Array.isArray(registry.provinceNameToCode)) {
  fail('region registry: provinceNameToCode must be an object');
}

const registryDir = dirname(registryPath);
const seenIds = new Set();
const seenProvinces = new Map();
const seenCodes = new Set();
const regionResults = [];
for (const region of registry.regions) {
  if (!region || typeof region !== 'object') fail('region registry: every region must be an object');
  const result = await validateRegion(region, registryDir, { country, level, codeSystem });
  if (seenIds.has(result.id)) fail(`region registry: duplicate id ${result.id}`);
  if (seenProvinces.has(result.province)) fail(`region registry: duplicate province ${result.province}`);
  if (seenCodes.has(result.provinceCode)) fail(`region registry: duplicate provinceCode ${result.provinceCode}`);
  seenIds.add(result.id);
  seenProvinces.set(result.province, result.provinceCode);
  seenCodes.add(result.provinceCode);
  regionResults.push(result);
}
for (const [name, codeValue] of Object.entries(registry.provinceNameToCode)) {
  const code = requireCode(codeValue, `region registry provinceNameToCode ${name}`);
  if (!seenCodes.has(code)) fail(`region registry provinceNameToCode ${name} points to unknown provinceCode ${code}`);
}
for (const [province, code] of seenProvinces) {
  if (String(registry.provinceNameToCode[province] ?? '') !== code) {
    fail(`region registry: missing provinceNameToCode mapping for ${province}`);
  }
}

const filterValue = process.argv.slice(2).find((arg) => arg.startsWith('--province='))?.split('=').slice(1).join('=');
const filtered = filterValue
  ? regionResults.filter((result) => result.province === filterValue || result.provinceCode === filterValue || registry.provinceNameToCode[filterValue] === result.provinceCode)
  : regionResults;
if (filterValue && filtered.length === 0) fail(`region registry: no resource package for ${filterValue}`);

console.log(`OK: ${filtered.length}/${regionResults.length} region packages validated`);
for (const result of filtered) {
  console.log(`- ${result.province} (${result.provinceCode}): ${result.cityCount} city codes, ${result.boundaryCount} matching offline boundaries, ${result.aliasCount} name aliases`);
  console.log(`  manifest: ${result.manifestPath}`);
  console.log(`  boundary: ${result.boundaryPath}`);
}
