const jwt = require("jsonwebtoken");


const authenticationToken=(req,res,next)=>{
    const authHeader= req.headers.authorization;

    if(!authHeader){
        return res.status(401).json({
            message:"Token requierd"
        });

    }

    const token= authHeader.split(" ")[1];
    try{
        const decoded=jwt.verify(token,"JWT_SECRET");

        req.user=decoded;
        next();
    }
    catch(error){
        return res.status(401).json({
            message:"Invalid token"
        })
    }
}

module.exports = authenticationToken;