const jwt = require('jsonwebtoken');

/**
 * Auth middleware – verifies the JWT from the Authorization header
 * and attaches { id } to req.user.
 */
module.exports = function authMiddleware(req, res, next) {
  const authHeader = req.header('Authorization');

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ msg: 'No token provided. Authorization denied.' });
  }

  const token = authHeader.slice(7); // strip "Bearer "

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    req.user = decoded.user; // { id }
    next();
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return res.status(401).json({ msg: 'Token has expired. Please log in again.' });
    }
    return res.status(401).json({ msg: 'Invalid token. Authorization denied.' });
  }
};
