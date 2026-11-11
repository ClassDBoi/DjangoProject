/**
 * Researcher headshots (the client will provide them).
 *
 * To add one:
 *   1. Put the image in frontend/public/headshots/ (JPG or PNG, square, at least 160x160 px),
 *      ideally named after the researcher's AUID, e.g. ABC1234.jpg.
 *   2. Add a line below. The key is the researcher's AUID exactly as in the database.
 *
 * Example:
 *   ABC1234: "/headshots/ABC1234.jpg",
 *
 * Researchers without a photo show their initials instead.
 */
const researcherPhotos = {
};

export default researcherPhotos;
