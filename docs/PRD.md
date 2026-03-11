# GeoBox - Product Requirements Document (PRD)

**Product Name**: GeoBox - AI-Powered Geospatial Metadata Intelligence for Box
**Version**: 2.0 (Multi-Agent Architecture)
**Owner**: AI Dev Days Hackathon Team
**Last Updated**: 2026-02-15

---

## 1. Product Vision

**Problem Statement:**
GIS professionals, field crews, surveyors, and drone operators struggle to manage geospatial metadata across thousands of photos and videos. ExifTool is powerful but CLI-only and requires manual processing. Box Platform lacks automatic GPS metadata extraction and validation.

**Solution:**
GeoBox automatically extracts, validates, and enriches GPS metadata from photos/videos uploaded to Box using AI-powered multi-agent workflows, making geospatial intelligence instantly searchable and accessible.

**Value Proposition:**
- **For GIS Teams**: Automatic GPS extraction from field photos/videos
- **For Surveying Crews**: AI-validated coordinates prevent costly errors
- **For Drone Operators**: Automatic GPX track generation from flight videos
- **For Box Admins**: Rich metadata visible directly in Box preview

---

## 2. Target Users

### Primary Users
1. **GIS Professionals** - Manage spatial data from field crews
2. **Surveyors** - Need accurate GPS coordinates from field photos
3. **Drone Operators** - Generate flight paths from video metadata
4. **Field Crews** - Upload photos from mobile devices, need automatic processing

### Secondary Users
5. **Box Administrators** - Manage enterprise content with geospatial context
6. **Researchers** - Analyze location data from photo collections

---

## 3. Core Features & Requirements

### 3.1 GPS Extraction (P0 - Critical)
**User Story**: As a GIS professional, I want GPS coordinates automatically extracted from uploaded photos so I don't have to manually process files with ExifTool.

**Requirements**:
- Extract latitude, longitude, altitude from EXIF/XMP metadata
- Support photos: JPG, PNG, HEIC
- Support videos: MP4, MOV, AVI
- Processing time: < 10 seconds per file
- Accuracy: 100% extraction when GPS data exists

**Acceptance Criteria**:
- [x] ✅ Box webhook triggers on FILE.UPLOADED
- [x] ✅ File downloaded and processed within 10 seconds
- [x] ✅ GPS coordinates extracted using ExifTool
- [x] ✅ Supports all target file formats

### 3.2 AI Validation (P0 - Critical)
**User Story**: As a surveyor, I want AI to validate GPS coordinates are plausible so I can catch errors before they cause costly rework.

**Requirements**:
- Detect impossible coordinates (out of range)
- Detect improbable locations (e.g., ocean when expecting land)
- Confidence score 0.0-1.0
- Graceful fallback if AI unavailable

**Acceptance Criteria**:
- [x] ✅ Basic validation (lat: -90 to 90, lon: -180 to 180)
- [ ] ⏸️ AI-powered anomaly detection (requires GPT quota)
- [x] ✅ Graceful fallback working
- [x] ✅ Confidence score calculated

### 3.3 Box Metadata Enrichment (P0 - Critical)
**User Story**: As a Box user, I want GPS metadata visible in Box file preview so I can quickly verify location without downloading.

**Requirements**:
- Write GPS data to Box metadata template
- Metadata visible in Box web UI preview
- Searchable by GPS coordinates in Box
- Support batch operations

**Acceptance Criteria**:
- [x] ✅ Metadata template created: `geoBoxIntelligence`
- [x] ✅ GPS data written to Box files
- [x] ✅ Visible in Box preview sidebar
- [ ] ⏸️ Box search by GPS (future)

### 3.4 GPX Track Generation (P1 - High Priority)
**User Story**: As a drone operator, I want automatic GPX tracks generated from flight videos so I can visualize flight paths in GIS software.

**Requirements**:
- Extract GPS track points from drone videos (DJI, GoPro)
- Generate valid GPX XML format
- Upload GPX file to same Box folder as source video
- Support continuous GPS logging formats

**Acceptance Criteria**:
- [ ] 📋 Extract GPS track from DJI drone videos
- [ ] 📋 Generate GPX XML format
- [ ] 📋 Upload to Box alongside source video
- [ ] 📋 Support GoPro format

### 3.5 Multi-Agent Architecture (P0 - Critical for Hackathon)
**User Story**: As a hackathon judge, I want to see advanced use of Microsoft Agent Framework and MCP so I can assess technical sophistication.

**Requirements**:
- Microsoft Agent Framework orchestrator
- MCP servers for ExifTool, Geospatial, Box operations
- Agent-driven workflow decisions (not hardcoded)
- Tool calling via MCP protocol

**Acceptance Criteria**:
- [x] ✅ Agent Framework orchestrator implemented
- [x] ✅ ExifTool MCP server working
- [x] ✅ Geospatial MCP server (deployed)
- [ ] 📋 Box MCP server (optional)
- [x] ✅ Autonomous agent decision-making

---

## 4. Non-Functional Requirements

### 4.1 Performance
- **Processing Time**: < 10 seconds per file (P0)
- **Throughput**: Support 100+ files/hour (P1)
- **Cold Start**: < 15 seconds container wake-up (P2)

**Status**: ✅ Meeting all performance targets

### 4.2 Scalability
- **Horizontal Scaling**: Support 0-10 container replicas (P0)
- **Scale-to-Zero**: Cost optimization when idle (P0)
- **Batch Processing**: Queue-based for high volume (P1)

**Status**: ✅ Scale-to-zero working, batch processing future

### 4.3 Reliability
- **Uptime**: > 99% availability (P1)
- **Error Handling**: Graceful degradation (P0)
- **Retry Logic**: Exponential backoff (P2)

**Status**: ✅ Graceful degradation implemented

### 4.4 Security
- **Authentication**: Box JWT app credentials (P0)
- **Webhook Verification**: Signature validation (P1)
- **Secrets Management**: Azure Key Vault (P1)

**Status**: ⚠️ JWT working, webhook signatures TODO

### 4.5 Cost
- **Budget**: < $20/month for hackathon (P0)
- **Production**: < $100/month estimated (P1)

**Status**: ✅ ~$11-20/month (3 container apps), well within budget

---

## 5. Technical Architecture Requirements

### 5.1 Cloud Infrastructure
- **Platform**: Azure (hackathon requirement)
- **Hosting**: Azure Container Apps (P0)
- **IaC**: Bicep templates (P0)
- **CI/CD**: Automated deployment (P1)

**Status**: ✅ Complete with Bicep

### 5.2 AI/ML Services
- **LLM**: Azure OpenAI GPT-4o (P0)
- **Agent Framework**: Microsoft Agent Framework (P0)
- **MCP**: Model Context Protocol servers (P0)

**Status**: ✅ Agent Framework + MCP implemented

### 5.3 Integrations
- **Box Platform**: Webhooks + Metadata API (P0)
- **ExifTool**: GPS extraction (P0)
- **Geospatial APIs**: Reverse geocoding (P1)

**Status**: ✅ Box working, geospatial APIs deployed (Nominatim + Open-Elevation)

---

## 6. User Experience Requirements

### 6.1 Box User Experience
**Interaction Model**: Zero-touch automation
- User uploads photo to Box
- GPS metadata appears automatically (< 10 seconds)
- No manual interaction required

**Status**: ✅ Working end-to-end

### 6.2 Metadata Display
**Requirements**:
- Readable field labels (e.g., "GPS Latitude" not "latitude")
- Color-coded validation status (valid=green, flagged=yellow)
- Helpful AI notes explaining validation

**Status**: ✅ Metadata visible, UI polish optional

### 6.3 Error States
**Requirements**:
- Clear error messages when GPS not found
- Suggest actions (e.g., "Upload a geotagged photo")
- Log errors for admin troubleshooting

**Status**: ✅ Error handling implemented

---

## 7. Success Criteria

### Hackathon Judging Criteria
1. **✅ Technical Innovation**: Multi-agent + MCP architecture
2. **✅ Use of Hero Technologies**: Agent Framework, MCP, Azure AI
3. **✅ Business Value**: Solves real GIS community problem
4. **✅ Completeness**: End-to-end working demo
5. **✅ Code Quality**: Production-ready, documented, tested

### Measurable Outcomes
- **Processing Success Rate**: > 95% ✅ (100% when GPS exists)
- **Processing Time**: < 10 seconds ✅ (~3 seconds average)
- **Cost Efficiency**: < $20/month ✅ (~$11-20/month)
- **User Adoption**: N/A (hackathon demo)

---

## 8. Out of Scope (Future Enhancements)

### Not for Hackathon Submission
- [ ] Mobile app for field crews
- [ ] Real-time GPS tracking
- [ ] Advanced GIS analysis (heatmaps, clustering)
- [ ] Multi-tenancy support
- [ ] GDPR compliance (location data privacy)
- [ ] Integration with ArcGIS, QGIS
- [ ] Blockchain for GPS provenance

### Deferred to Post-Hackathon
- [ ] Batch processing queue
- [ ] Webhook signature verification
- [ ] Azure Key Vault secrets
- [ ] Full GPX generation (all video formats)
- [x] Reverse geocoding (address from coordinates) — deployed via Geo MCP
- [x] Elevation API integration — deployed via Geo MCP

---

## 9. Feature Prioritization

### P0 - Must Have (Hackathon Submission)
- [x] GPS extraction from photos/videos
- [x] Basic AI validation (with fallback)
- [x] Box metadata enrichment
- [x] Multi-agent architecture (Agent Framework)
- [x] MCP server (ExifTool)
- [x] MCP server (Geo — reverse geocoding + elevation)
- [x] Azure deployment (Container Apps)
- [x] IaC (Bicep templates)

### P1 - Should Have (If Time Permits)
- [ ] GPX track generation
- [x] Geospatial MCP server (reverse geocoding) — deployed
- [ ] Box MCP server (operations)
- [ ] Advanced AI validation (anomaly detection)
- [ ] Webhook signature verification

### P2 - Nice to Have (Future)
- [ ] Batch processing
- [ ] Performance dashboards
- [ ] Cost monitoring alerts
- [ ] Multi-agent collaboration workflows

---

## 10. Dependencies & Risks

### External Dependencies
- **Azure OpenAI**: Graceful fallback if quota unavailable
- **Box Platform**: Stable API
- **ExifTool**: Open source, stable
- **Agent Framework**: Beta software (1.0.0b)

### Technical Risks
1. **Agent Framework Beta**: Mitigated with fallback mode
2. **MCP Protocol New**: Mitigated with HTTP transport
3. **Azure Quota Limits**: Mitigated with graceful degradation

### Schedule Risks
- Deployment complete, on track for submission

---

## 11. Release Plan

### Phase 1: Hackathon Demo (Current)
- **Target**: March 15, 2026
- **Status**: ✅ Ready to submit
- **Features**: All P0 features complete

### Phase 2: Production Beta (Post-Hackathon)
- **Target**: Q2 2026
- **Features**: P1 features + security hardening

### Phase 3: General Availability
- **Target**: Q3 2026
- **Features**: Full feature set + multi-tenancy

---

## 12. Open Questions

1. **GPX Video Formats**: Which drone formats to prioritize? (DJI vs GoPro)
2. **Geospatial APIs**: Which reverse geocoding service? (OSM vs Google vs Azure)
3. **Box Search Integration**: How to enable GPS-based search in Box?
4. **Azure OpenAI Quota**: Request increase or continue with fallback?

---

## 13. Appendix

### Related Documents
- **Technical Architecture**: [architecture.md](architecture.md)
- **Deployment Guide**: [deployment_guide.md](deployment_guide.md)
